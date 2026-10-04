# Execution runbook

## Immediate snapshot verification

From the repository root, Python 3.12 is sufficient; the core has no pip dependencies:

```powershell
python -m unittest discover -s tests -v
python src/data_processing/validate_portfolio.py --verify-snapshot --output work/quality_check.json
```

Snapshot mode checks the exact submitted bytes and baseline totals. A new pipeline
output uses contract validation without `--verify-snapshot`, because corrections
and stricter evidence acceptance can legitimately change values and fingerprints.
The validator exits 0 on PASS, 1 on failed checks and 2 on input/argument errors.

## Local recovery in Visual Studio Code

1. Open the complete folder and select Python 3.12.
2. Obtain the original portfolio, not the reporting export. Required raw columns:
   `ClientId, policy_id, client_name, state, municipality, coverage_type, industry,
   premium, sum_insured, policy_start_date, policy_end_date`. Missing industry is blank;
   other required fields must be usable. IDs remain strings, amounts use Decimal,
   dates accept ISO or day/month/year. Extra provenance columns are refused.
3. Put the CSV in `data/raw/portfolio_original.csv` (not tracked).
4. Copy and edit config, then run from the root:

```powershell
Copy-Item config/pipeline.example.json config/pipeline.local.json
python -m src.pipeline --config config/pipeline.local.json
```

Paths in the example are relative to the config file, not the terminal directory.
Use a new empty output directory for every complete run. Stage artifacts are also
protected against overwrite, so partially failed runs need a new directory.
The CLI exits 2 if a stage stops. No generated result overwrites the submitted CSV.

Individual stages, useful for inspection before continuing:

```powershell
python -m src.pipeline --config config/pipeline.local.json --stage eda
python -m src.pipeline --config config/pipeline.local.json --stage recover
python -m src.pipeline --config config/pipeline.local.json --stage enrich
python -m src.pipeline --config config/pipeline.local.json --stage report
```

Use these four commands instead of `all` for the same run, not afterwards.
The optional ML notebook can be run after recovery; it is not a fill dependency.
Individual stages emit diagnostics; a complete CLI run also writes `run_manifest.json`.

## Databricks

Use a Git folder containing the full repository and the same private config.
Choose one source, for example:

```json
{
  "input_path": "",
  "input_table": "catalog.schema.portfolio_mexico",
  "output_dir": "/Volumes/catalog/schema/volume/runs/run_001",
  "external_results_path": "",
  "contract_path": "portfolio_contract.json"
}
```

Alternatively set `input_path` to an original CSV under `/Volumes/...` and leave
`input_table` empty. Set each notebook's `config_path` widget to this config.
Run 01, 02, optional 03, 04, 05, then 06. In 06 the private config automatically selects the generated CSV without
snapshot mode; without config it checks the included submission. INPUT_PATH and
VERIFY_SNAPSHOT can explicitly override that selection.
Python `Path` uses `/Volumes/...`, not `dbfs:/...` URIs. Compute must have permissions
to read the source and write the chosen Volume. This code has not been run in the
candidate's actual Databricks workspace.

The shared core runs on the driver with a hard 100,000-row limit before collection.
The optional Spark EDA is in `notebooks/research/portfolio_eda_spark.py`.

## Modeling research

Run `notebooks/03_industry_modeling.py` after stage 02. It retains the candidate's
feature engineering, model families, alternative experiments and controls.
The reviewed version reserves the holdout before label diagnostics and limits
robustness experiments to development clients; it also fits OVR scaling per fold.
It prints results, saves CV folds/comparison, client splits, holdout metrics
and actual package versions in `03_modeling/`, and does not create industry fills. Historical scores must be rerun.

On Databricks, install `requirements-modeling.txt` in the compute environment and
restart Python if needed before opening the notebook. Do not replace runtime
Spark with a local pip Spark installation. On Windows/local VS Code:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements-spark-local.txt
$env:CHUBB_CONFIG = "config/pipeline.local.json"
python notebooks/03_industry_modeling.py
```

Local Spark needs Java 17+ and a working Spark setup. Pins are a reviewed proposal;
the original runtime/package export and full fit validation are still missing.
Early-stopping CV metrics are development estimates; report holdout performance
separately. Do not use historical metrics as outputs from the refactored code.

## Saved external evidence and optional live research

By default `external_results_path` is empty: all residual clients abstain. A reviewed
cache CSV must contain one row per unresolved ClientId and these columns:

```text
ClientId,candidate_industry,entity_found,entity_confidence,industry_confidence,
verification_level,grounding_sources,error_message,matched_company_name,
matched_legal_name,economic_activity,evidence_summary
```

`entity_found` is true/false; `grounding_sources` is a JSON array of source identifier
strings. Empty sources, service errors, unknown labels, insufficient confidence or
nonofficial verification cause abstention. Duplicates and already-resolved/stale
clients stop processing. The audit retains accepted and rejected evidence.
Set the path to this cache in a fresh pipeline config and run again.

To generate NEW live evidence, separately use
`notebooks/research/external_enrichment_live.py` in Databricks. As documented by
Databricks, `ai_enrich` needs Runtime 18.2+ (serverless environment 3+) and enabled
workspace capabilities. Availability and service usage depend on the workspace.
Add `allow_live_enrichment: true` and a fresh absolute `/Volumes/...` directory as
`live_output_dir` to the private config; choose `backtest` first in the widget.
The notebook sends names/locations, not ClientIds or true industries, and stores raw
responses before displaying/counting. Choose a new directory for every live run.
No live request was executed during this review. Backtest caches cannot be replayed
as production fills. Source metadata supports row grounding, not independently
verified correctness of each industry. Preserve errors and review source matches.

## Generated artifacts

| Artifact | Purpose |
| --- | --- |
| `01_eda.json` | Aggregate raw analysis and known-row LOO coverage |
| `02_recovered.csv` | Original columns, industry_filled and fill_method |
| `02_recovery_summary.json` | Same-client recovery counts |
| `04_enriched.csv` | Original industry plus final industry/method/confidence |
| `04_external_audit.csv` | Full evidence and acceptance/rejection reason |
| `04_external_summary.json` | Replay mode and client counts |
| `05_name_lineage.csv` | Chosen name, family and reference policy |
| `portfolio_reporting.csv` | Contract-validated UTF-8 CSV for Power BI |
| `06_validation.json` | Counts, exact premium and data-quality diagnostics |
| `run_manifest.json` | Complete CLI-run status and artifact fingerprints |

Raw input, private config, evidence and generated artifacts are excluded from Git.
Review deliberate publication separately from running code.

References: [Databricks Python modules](https://docs.databricks.com/aws/en/files/workspace-modules),
[ai_enrich specification](https://learn.microsoft.com/en-us/azure/databricks/sql/language-manual/functions/ai_enrich),
[scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).
