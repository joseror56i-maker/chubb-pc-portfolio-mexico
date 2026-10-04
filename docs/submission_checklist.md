# Submission checklist

Assessment requirements are distinguished from user authorization. The repository
is public at the candidate's request; supplied reporting data has been published.

| Deliverable | Present | Remaining work |
| --- | --- | --- |
| Public repository with solution code | Reviewed processing, ML, enrichment and sequential notebooks | Run with original inputs and record actual environment |
| README | Setup, layout, sequence and limitations | Update after dashboard integration |
| Filled dataset with per-row method | Unchanged submitted snapshot | Reconcile against original input and saved evidence |
| Fill quality report | Counts and amounts verified | Rerun corrected research and review external correctness |
| Interactive premium/growth dashboard | Not yet supplied | PBIX/PBIP, preview, DAX review and download/refresh test |
| Short technical write-up | Present with historical appendix | Attach fresh experiment outputs |

Before final submission:

- Validate snapshot and run unit tests from a fresh clone/download.
- Run the reviewed pipeline on the original dataset and audit source labels and amounts.
- Record Databricks runtime, package versions, seeds, holdout and experiment outputs.
- Supply/audit the external mapping; treat historical external fills as weak evidence.
- Add and test the dashboard after receiving its file.
- Reconcile BI totals: 50,441 policies; 8,565 clients; premium 23,465,362,773.10.
- Validate equivalent growth periods, currency assumption and the dominant-client view.
- Keep credentials, raw private inputs and machine-specific config outside Git.
