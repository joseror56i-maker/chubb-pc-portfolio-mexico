# Submission Checklist

The six required deliverables below come from the supplied technical challenge.
They describe assessment requirements, not authorization to publish confidential
input or create additional services.

| Deliverable | Present in this package | Remaining work |
| --- | --- | --- |
| Public GitHub repository with all solution code | Organized initial package and new validator | Add and review the original processing/modeling source; finish publication |
| README | Yes | Update status when missing artifacts arrive |
| Filled dataset with per-row method | Yes, unchanged renamed snapshot | Confirm publication rights and raw-to-final lineage |
| Fill quality report | Yes, counts reconciled | Reproduce historical experiments and review external evidence |
| Interactive premium/growth dashboard | No | Supply PBIX/PBIP, preview and test download/refresh |
| Short technical write-up | Yes, with detailed appendix | Attach reproducible experiment outputs |

Before final submission:

- Run validator, snapshot verification and unit tests from a fresh copy/clone.
- Run the complete original pipeline in the documented environment.
- Record dependencies, seeds and runtime versions from the actual source.
- Verify no original industry labels were overwritten and no join multiplied rows.
- Confirm publication rights for the dataset and any embedded Power BI data.
- Test download, opening and refresh of the dashboard from another folder.
- Reconcile dashboard totals to 50,441 policies, 8,565 clients and premium
  23,465,362,773.10 in source currency units.
- Review same-period growth and exclude unavailable prior-year values from
  percentage calculations instead of fabricating zero growth.
- Keep a clean commit history with meaningful messages and no credentials.
