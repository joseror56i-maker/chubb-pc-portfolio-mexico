# Modeling research

`diagnostics.py` contains the missing correlation-ratio function as reusable,
dependency-free code. The complete reviewed experiment is in
`notebooks/03_industry_modeling.py`, retaining the candidate's diagnostic narrative
and model comparisons. Notebook orchestration makes the split and feature context
visible; fitted preprocessing stays inside the benchmark functions.

Models never feed reporting industry. Historical scores were not rerun; corrected
holdout isolation, fold scaling and deterministic ordering require fresh evaluation.
Optional package pins are in `requirements-modeling.txt`; the original environment
export is still needed. See the execution runbook and review notes.
