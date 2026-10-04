# Submission checklist

The assessment requests exactly six deliverables. Solution code is delivered
through the public GitHub repository; a handoff folder contains the link,
README, reporting CSV, quality report, complete dashboard and short write-up.

| Deliverable | Present | Remaining work |
| --- | --- | --- |
| Public repository with solution code | Reviewed processing, ML, enrichment and sequential notebooks; 31 tests pass | Run optional research and record actual environment |
| README | Setup, layout, sequence, decisions and assumptions | Present; keep aligned with future changes |
| Filled dataset with per-row method | Unchanged submitted snapshot | Original lineage reconciled; external evidence audit still separate |
| Fill quality report | Counts and amounts verified | Rerun corrected research and review external correctness |
| Interactive premium/growth dashboard | PBIP integrated, portable setup and dependency checks | Desktop refresh/render and preview |
| Short technical write-up | Present with historical appendix | Attach fresh experiment outputs |

Before final submission:

- Validate snapshot and run unit tests from a fresh clone/download.
- Original-to-reporting reconciliation has passed for IDs, amounts, dates, original
  industries, same-client recovery and canonical names.
- Record Databricks runtime, package versions, seeds, holdout and experiment outputs.
- Supply/audit the external mapping; treat historical external fills as weak evidence.
- Open/refresh the packaged dashboard in Desktop and capture an actual preview.
- Reconcile BI totals: 50,441 policies; 8,565 clients; premium 23,465,362,773.10.
- Validate equivalent growth periods, currency assumption and the dominant-client view.
- Keep credentials, raw private inputs and machine-specific config outside Git.
