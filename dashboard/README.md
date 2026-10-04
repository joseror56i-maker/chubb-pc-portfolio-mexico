# Power BI Dashboard: Packaging and Refresh

The dashboard file has not yet been supplied. The following is a preparation plan;
it is not a review of the actual connections, DAX, visuals or file compatibility.

## Recommended delivery after review

- `premium_growth_dashboard.pbix`: reviewer-friendly downloadable dashboard.
- `../data/processed/portfolio_reporting.csv`: stable local refresh input.
- `../assets/dashboard_preview.png`: screenshot of the actual report.
- This guide: required Power BI Desktop version, source parameter and refresh steps.
- Optional PBIP source project: retain its report and semantic model together for
  version control. Do not substitute it for a tested downloadable PBIX silently.

Prefer Import mode for a standalone assessment file if the model supports it, so
saved visuals can be viewed without a live Databricks or Power BI Service session.
Refresh still needs a valid data source. A PBIX with a live connection can require
access to the remote semantic model even after download.

## Source parameter

Create one text parameter such as `PortfolioCsvPath` for the CSV location. The
Power Query source should use that parameter, rather than an author-specific
OneDrive or Desktop path. Document how to change it before refresh. Power BI does
not automatically resolve a CSV relative to the PBIX just because they are zipped
together; an explicit parameter is needed.

Parse comma-separated UTF-8 CSV with proper quoting, text identifiers, ISO dates
and an explicit numeric locale. Keep all 13 reporting column names stable. Change
the parameter to the new `portfolio_reporting.csv` name without dropping and
recreating the report table or its measures unnecessarily.

## Risks to inspect in the supplied file

| Risk | Download/refresh impact | Verification |
| --- | --- | --- |
| Hardcoded author path | Refresh fails on another computer | Parameterize the source and refresh from a new directory |
| DirectQuery or live model | Remote access is needed | Inspect storage mode and every connection |
| Renamed file / schema drift | Power Query or DAX references break | Preserve columns and retarget the source parameter |
| Locale / encoding | Dates, amounts or accents are misread | Explicit parsing and reconciliation against the CSV |
| Wrong calendar date | Growth includes end-date years through 2026 | Review calendar relationship and same-period calculation |
| Client-name grouping | Distinct clients collapse into one label | Client dimension keyed by `ClientId` |
| External candidates | Low-confidence industry changes segment metrics | Show provenance and sensitivity without dropping premium |
| Desktop version / custom visuals | File or visuals may not load | Record the tested version and inspect visual dependencies |
| Embedded client data | A public PBIX can expose imported policy data | Verify publication rights; a hidden page is not data removal |
| Git LFS pointer in ZIP | Downloaded PBIX is a small text pointer | Test the actual download or publish a complete release ZIP |

## GitHub file handling

The CSV is 8,639,786 bytes (8.24 MiB), below the 25 MiB browser upload limit.
GitHub command-line uploads allow files up to 100 MiB. Measure the PBIX before
choosing ordinary Git, Git LFS, or a Release asset. If using LFS, generated source
archives can omit the actual binary depending on repository archive settings;
test the ZIP rather than assuming it contains a usable dashboard.

A complete tested Release ZIP containing the PBIX, CSV and this refresh guide is
often convenient for evaluators. Extract it, open the PBIX, set the CSV parameter
and refresh. A service link or screenshot alone does not establish downloadability.

## Download test

1. Download the package and extract it into a different folder.
2. Open the PBIX in the documented Power BI Desktop version.
3. If Import mode was used, check saved visuals before accessing any remote source.
4. Change `PortfolioCsvPath` to the extracted CSV and refresh.
5. Reconcile 50,441 policies, 8,565 clients and premium 23,465,362,773.10.
6. Check first-year growth, zero/absent denominators and equivalent period filters.
7. Confirm all industry/location filters and `Unresolved` selections work.
8. Check concentration and external-fill sensitivity without altering official totals.

## Official references

- [Power Query parameters](https://learn.microsoft.com/en-us/power-query/power-query-query-parameters)
- [Power BI data sources](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-sources)
- [Download modes and limitations](https://learn.microsoft.com/en-us/power-bi/create-reports/service-export-to-pbix)
- [Power BI projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview)
- [GitHub file upload limits](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
- [Git LFS and archives](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
