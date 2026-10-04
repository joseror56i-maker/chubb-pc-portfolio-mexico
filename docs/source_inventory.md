# Source mapping

The candidate supplied five Databricks source exports in `Prueba Tecnica Chubb.zip`.
This table maps each original file to its reviewed implementation; duplicate fills,
dead SDK installation/imports and temporary CatBoost logs were removed.

| Supplied file | Reviewed destination |
| --- | --- |
| `0. EDA.py` | `01_portfolio_eda.py`, shared raw diagnostics, optional Spark visual EDA in `research/portfolio_eda_spark.py` |
| `1. Imputacion por ID.py` | `02_recover_industry_by_client.py` and `src/data_processing/recovery.py` |
| `3. Industry_Imputation_ML.py` | `03_industry_modeling.py` and `src/modeling/diagnostics.py` |
| `2. LLM Client Resolution.py` | Shared replay/acceptance in `external.py`, preserved prompt/schema in `src/enrichment/prompt.py`, service adapter and optional live notebook |
| `Client_Name_Normalization_Reporting_FINAL_v2.py` | `05_build_reporting_dataset.py`, `names.py`, explicit CSV export and final validator |

The names rank preserves the original priorities: most frequent match family,
largest word count/length, earliest date, lexical tie break; within the family,
richest observed name, non-uppercase preference, frequency/date/name tie breaks.
Matching removes accents/punctuation/legal suffixes; display names retain them.
Reference policy lineage is exported rather than dropped from the deliverable.

The ML notebook retains LightGBM, XGBoost, CatBoost, client/policy/name features,
statistical diagnostics, clustering, OVR and positive/negative controls. Holdout
isolation and OVR scaling were corrected, so historical metrics require a rerun.
The additional original LLM smoke tests and intermediate displays are condensed
into a reproducible client-level backtest and a separately enabled live run.

The reporting snapshot remains exactly the candidate's supplied artifact. Raw
inputs and saved responses were absent from the code ZIP. No original script was
executed to train models, overwrite a workspace table or call an external service.
