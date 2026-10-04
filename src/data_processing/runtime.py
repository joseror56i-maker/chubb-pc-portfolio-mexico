"""Configurable I/O and sequential stages shared by the CLI and notebooks."""

import csv
import json
import hashlib
import sys
from pathlib import Path
from .recovery import RAW_COLUMNS, prepare_raw, describe_portfolio, recover_by_client
from .external import EVIDENCE_COLUMNS, apply_external
from .names import build_reporting
from .validate_portfolio import validate_portfolio

ROOT = Path(__file__).resolve().parents[2]
MAX_DRIVER_ROWS = 100_000


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    # Relative paths refer to the config file's directory, never the shell's cwd.
    for key in ("input_path", "output_dir", "external_results_path", "contract_path"):
        if config.get(key):
            value = Path(config[key])
            config[key] = str(value if value.is_absolute() else (path.parent / value).resolve())
    if not config.get("output_dir"):
        raise ValueError("Set an output_dir for generated artifacts")
    if not config.get("input_path") and not config.get("input_table"):
        raise ValueError("Set input_path (CSV) or input_table (Databricks)")
    if config.get("input_path") and config.get("input_table"):
        raise ValueError("Choose exactly one raw input source")
    config.setdefault("contract_path", str(ROOT / "config/portfolio_contract.json"))
    output = Path(config["output_dir"]).resolve()
    if (
        output == (ROOT / "data/processed").resolve()
        or (ROOT / "data/processed").resolve() in output.parents
    ):
        raise ValueError("Use a new run directory; the submitted snapshot is protected")
    if config.get("input_path") and (
        output == Path(config["input_path"]).parent or output in Path(config["input_path"]).parents
    ):
        raise ValueError("Keep raw input outside the generated output directory")
    return config


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Missing or duplicate CSV headers")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row")
            rows.append(row)
            if len(rows) > MAX_DRIVER_ROWS:
                raise ValueError("Portfolio exceeds the documented driver row limit")
        return rows


def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Stage to a temporary sibling so interrupted writes never become inputs.
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def load_raw(config, spark=None):
    contract = json.loads(Path(config["contract_path"]).read_text(encoding="utf-8"))
    if config.get("input_table"):
        if spark is None:
            raise ValueError("input_table requires Databricks Spark; use input_path locally")
        frame = spark.table(config["input_table"])
        # Bound driver memory before collection; this project is a 50k-policy task.
        sampled = frame.limit(MAX_DRIVER_ROWS + 1).collect()
        if len(sampled) > MAX_DRIVER_ROWS:
            raise ValueError("Portfolio exceeds the documented driver row limit")
        rows = [row.asDict() for row in sampled]
        rows.sort(key=lambda r: (str(r.get("ClientId", "")), str(r.get("policy_id", ""))))
    else:
        rows = read_csv(config["input_path"])
    return prepare_raw(rows, set(contract["industry_labels"]) - {contract["unresolved_label"]})


def run_stage(stage, config, spark=None):
    """Execute one reproducible stage; paid research is deliberately a separate job."""
    output = Path(config["output_dir"])
    contract = json.loads(Path(config["contract_path"]).read_text(encoding="utf-8"))
    stage_files = {
        "eda": ("01_eda.json",),
        "recover": ("02_recovered.csv", "02_recovery_summary.json"),
        "enrich": ("04_enriched.csv", "04_external_audit.csv", "04_external_summary.json"),
        "report": (
            "portfolio_reporting.csv",
            "portfolio_reporting.candidate.csv",
            "05_name_lineage.csv",
            "06_validation.json",
        ),
    }
    if any((output / name).exists() for name in stage_files.get(stage, ())):
        raise ValueError("Stage outputs already exist; choose a fresh run directory")
    if stage == "eda":
        result = describe_portfolio(load_raw(config, spark))
        write_json(output / "01_eda.json", result)
    elif stage == "recover":
        raw = load_raw(config, spark)
        rows = recover_by_client(raw)
        write_csv(
            output / "02_recovered.csv", rows, (*RAW_COLUMNS, "industry_filled", "fill_method")
        )
        result = {
            "rows": len(rows),
            "method_counts": {
                method: sum(r["fill_method"] == method for r in rows)
                for method in ("original", "client_id", "unresolved")
            },
        }
        write_json(output / "02_recovery_summary.json", result)
    elif stage == "enrich":
        rows = read_csv(output / "02_recovered.csv")
        evidence = (
            read_csv(config["external_results_path"]) if config.get("external_results_path") else []
        )
        rows, audit = apply_external(
            rows, evidence, set(contract["industry_labels"]) - {contract["unresolved_label"]}
        )
        write_csv(
            output / "04_enriched.csv",
            rows,
            (
                *RAW_COLUMNS,
                "industry_filled",
                "fill_method",
                "industry_final",
                "fill_method_final",
                "confidence_level",
            ),
        )
        write_csv(
            output / "04_external_audit.csv", audit, (*EVIDENCE_COLUMNS, "acceptance_decision")
        )
        result = {
            "cached_clients": len(evidence),
            "accepted_clients": sum(r["acceptance_decision"] == "accepted" for r in audit),
            "mode": "saved_evidence_replay" if evidence else "no_external_evidence",
        }
        write_json(output / "04_external_summary.json", result)
    elif stage == "report":
        rows, lineage = build_reporting(read_csv(output / "04_enriched.csv"), contract["columns"])
        candidate = output / "portfolio_reporting.candidate.csv"
        write_csv(candidate, rows, contract["columns"])
        result = validate_portfolio(candidate, config["contract_path"])
        write_json(output / "06_validation.json", result)
        if result["status"] != "PASS":
            raise ValueError("Generated reporting data failed its contract; see 06_validation.json")
        candidate.replace(output / "portfolio_reporting.csv")
        write_csv(
            output / "05_name_lineage.csv",
            lineage,
            (
                "ClientId",
                "client_name_reporting",
                "reference_policy_id",
                "reference_start_date",
                "reference_raw_name",
                "match_family",
                "variant_count",
                "family_count",
            ),
        )
    else:
        raise ValueError(f"Unknown stage: {stage}")
    return result


def run_pipeline(config, spark=None):
    """Use a fresh directory to prevent artifacts from separate runs being mixed."""
    output = Path(config["output_dir"])
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output_dir for a complete run")
    results = {
        stage: run_stage(stage, config, spark) for stage in ("eda", "recover", "enrich", "report")
    }
    artifacts = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.iterdir())
        if path.is_file()
    }
    inputs = {
        key: hashlib.sha256(Path(config[key]).read_bytes()).hexdigest()
        for key in ("input_path", "external_results_path", "contract_path")
        if config.get(key)
    }
    write_json(
        output / "run_manifest.json",
        {
            "stages": results,
            "artifact_sha256": artifacts,
            "input_sha256": inputs,
            "python_version": sys.version.split()[0],
            "ml_used_for_imputation": False,
            "external_live_calls": False,
        },
    )
    return results
