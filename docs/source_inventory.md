# Code architecture

| Stage | Notebook | Shared implementation |
| --- | --- | --- |
| Raw EDA | `01_portfolio_eda.py` | `src/data_processing/recovery.py`; optional Spark visual analysis in `research/portfolio_eda_spark.py` |
| Recovery by client | `02_recover_industry_by_client.py` | `src/data_processing/recovery.py` |
| ML evaluation | `03_industry_modeling.py` | `src/modeling/diagnostics.py` and benchmark functions within the research notebook |
| External research and replay | `04_replay_external_evidence.py`, optional live research | `src/data_processing/external.py` and `src/enrichment/` |
| Reporting names and export | `05_build_reporting_dataset.py` | `names.py`, runtime CSV export and reporting validator |
| Quality checks | `06_validate_reporting_dataset.ipynb` | CSV contract, original-lineage and project-dependency tests |
| Interactive reporting | `dashboard/premium_growth.pbix` and editable PBIP | Self-contained viewer, report definitions, TMDL and setup/build helpers |

Names are normalized within ClientId and retain reference-policy lineage.
ML predictions do not enter the final industry field. External entity research
uses the preserved prompt/schema and retains candidate evidence separately.
The final reporting CSV includes original, same-client, externally researched
and unresolved records with per-row method/confidence metadata.
