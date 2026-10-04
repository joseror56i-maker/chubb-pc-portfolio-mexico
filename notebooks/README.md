# Sequential notebooks

Databricks `.py` source notebooks contain `# COMMAND ----------` cell separators.
Clone the full repository in a Git folder and create `config/pipeline.local.json`.
VS Code runs the same core via `python -m src.pipeline`; optional ML can also be
run as a Python script with its separate Spark/modeling dependencies.

1. **01**: aggregate EDA from original input; no writes to source data.
2. **02**: recovery by ClientId, with conflict and row-preservation guards.
3. **03**: optional ML feasibility research, never an automatic fill step.
4. **04**: replay reviewed saved external evidence; default abstention, no network.
5. **05**: canonical names, reporting CSV, lineage and contract validation.
6. **06**: validate the included snapshot or select a generated CSV independently.

`research/portfolio_eda_spark.py` preserves distributed EDA displays and requires
a configured input table. `research/external_enrichment_live.py` generates new
external evidence only when explicitly enabled in private config.
See the [runbook](../docs/runbook.md) for exact setup and execution limits.
