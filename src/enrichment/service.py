"""Optional Databricks ai_enrich adapter; materialize each batch once.

This module performs live web/model requests only when the research notebook is
explicitly enabled. Normal pipeline runs replay a saved CSV without this module.
"""

import json
from pathlib import Path
from .prompt import enrichment_schema, instructions


def sql_literal(value):
    """Escape SQL literal content, including Spark's backslash parsing."""
    return value.replace("\\", "\\\\").replace("'", "''")


def enrich_batch(frame, batch_path):
    """Write raw VARIANT responses first, then read before any count/display.

    Spark is lazy: directly displaying and counting an AI expression can repeat
    paid requests. A fresh batch path also prevents old responses entering a run.
    """
    from pyspark.sql import functions as F

    schema = sql_literal(json.dumps(enrichment_schema, ensure_ascii=False))
    prompt = sql_literal(instructions)
    expression = f"""ai_enrich(
        search_context, '{schema}',
        parse_json('[{{"type":"web_search","config":{{}}}}]'),
        options => map('instructions', '{prompt}', 'enableRationale', 'true')
    )"""
    frame.withColumn("enrichment", F.expr(expression)).write.mode("errorifexists").parquet(
        str(batch_path)
    )
    saved = frame.sparkSession.read.parquet(str(batch_path))
    return extract_results(saved)


def extract_results(saved):
    """Retain source references and service errors alongside candidate labels."""
    from pyspark.sql import functions as F

    fields = {
        "entity_found": ("entity_found", "BOOLEAN"),
        "candidate_industry": ("industry", "STRING"),
        "matched_company_name": ("matched_company_name", "STRING"),
        "matched_legal_name": ("legal_name", "STRING"),
        "economic_activity": ("economic_activity", "STRING"),
        "entity_confidence": ("entity_confidence", "STRING"),
        "industry_confidence": ("industry_confidence", "STRING"),
        "verification_level": ("verification_level", "STRING"),
        "evidence_summary": ("evidence_summary", "STRING"),
    }
    return saved.select(
        "ClientId",
        *[
            F.expr(f"enrichment:response.{source}.value::{kind}").alias(target)
            for target, (source, kind) in fields.items()
        ],
        F.expr("CAST(enrichment:metadata.sources AS STRING)").alias("grounding_sources"),
        F.expr("enrichment:error_message::STRING").alias("error_message"),
    )


def context_frame(spark, rows):
    """Send names and locations to research; keep internal IDs out of the payload."""
    from pyspark.sql import functions as F

    frame = spark.createDataFrame(rows)
    return (
        frame.groupBy("ClientId")
        .agg(
            F.sort_array(F.collect_set("client_name")).alias("client_names"),
            F.sort_array(F.collect_set("state")).alias("states"),
            F.sort_array(F.collect_set("municipality")).alias("municipalities"),
        )
        .withColumn(
            "search_context", F.to_json(F.struct("client_names", "states", "municipalities"))
        )
    )


def research_run(spark, rows, output_dir, batch_size=50):
    """Create a fresh research directory and deterministic client batches.

    Results/errors are saved for inspection. Rerun failed clients in a new run;
    no blind retries or recursive reads of every historical batch are performed.
    The supplied workspace must support ai_enrich and VARIANT Parquet writes.
    """
    from pyspark.sql import functions as F
    from src.data_processing.runtime import write_csv
    from src.data_processing.external import EVIDENCE_COLUMNS

    output = Path(output_dir)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if output.exists():
        raise ValueError("Choose a new live research output directory")
    output.mkdir(parents=True)
    if not rows:
        write_csv(output / "external_evidence.csv", [], EVIDENCE_COLUMNS)
        return []
    frame = context_frame(spark, rows).cache()
    try:
        clients = sorted(str(row.ClientId) for row in frame.select("ClientId").collect())
        results = []
        for offset in range(0, len(clients), batch_size):
            selected = clients[offset : offset + batch_size]
            saved = enrich_batch(
                frame.filter(F.col("ClientId").isin(selected)),
                output / f"batch_{offset // batch_size:04d}",
            )
            results.extend(row.asDict() for row in saved.orderBy("ClientId").collect())
        write_csv(output / "external_evidence.csv", results, EVIDENCE_COLUMNS)
        return results
    finally:
        frame.unpersist()
