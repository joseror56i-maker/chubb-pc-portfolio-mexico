# Premium and growth dashboard

## Open the interactive submission

Download [premium_growth.pbix](premium_growth.pbix) using GitHub's **Download raw file**
button, or download/extract the repository ZIP. Open the PBIX in a recent
**Power BI Desktop for Windows**. GitHub does not run Power BI reports in its browser.

The PBIX contains imported data, the model, both report pages and all assets.
It opens and refreshes without the CSV, Python, a source project or personal paths.
Its Power Query source decompresses an embedded snapshot of the final CSV.
The CSV SHA-256 is `e29678677fe570b57f13aeec85cc51f5e4bcb477b51f5fcc8054794813a905c3`.

Overview and Detalle offer industry, state, municipality, coverage and client filters,
Premium/Premium Growth, cutoff-period YTD/Last Year, rankings and policy detail.
Saved filters use December 2023 and exclude the dominant client as a sensitivity.
Choose **Total portfolio** for official totals. Client labels combine ID and name.

## Source project and rebuilding

The editable PBIP, Report and SemanticModel folders remain included for development.
Keep all three together. Their CSV parameter is configured in an ignored local copy:

```powershell
python dashboard/setup_dashboard.py
```

Open `work/pbi/premium_growth.pbip`, then Refresh. This development workflow uses
the external reporting CSV and needs its path updated if that CSV moves.

To generate a project with an embedded snapshot:

```powershell
python dashboard/build_standalone.py
```

Open `work/pbi_standalone/premium_growth.pbip`, Refresh, then use **File > Save as >
Power BI file (*.pbix)**. The builder validates and compresses exact CSV bytes,
reuses the report/DAX definitions and removes the external file parameter.
Only Desktop creates the PBIX; Python generates the editable text source.
Choose a fresh output directory for each build. Review new data and calendar
coverage before releasing a replacement. Refresh of a snapshot does not fetch new data.

## Verification and practical limits

- Genuine Desktop save, independent PBIX reopen, embedded-data refresh and both
  report pages were checked on 2026-10-04.
- Read-only queries against the reopened model reconcile 50,441 policies,
  8,565 clients, 1,356 Unresolved and premium 23,465,362,773.10. Full-year premium
  and growth for 2021-2024 match independent CSV controls.
- See [runtime evidence](../reports/dashboard_runtime_validation.json),
  [static dependencies](../reports/dashboard_validation.json) and
  [review notes](../docs/dashboard_review.md). A full visual/business acceptance
  review remains the candidate's final check.
- The calendar and dominant-client rule must be reviewed for a different portfolio.
  YTD values depend on cutoff and saved filters; they are not four-year totals.
  Missing prior-year denominators remain blank. Currency is unspecified.
- The PBIX includes all submitted data. Publish/share it under the same data scope
  as the authorized reporting CSV. No Power BI Service publication was performed.

References: [Power BI projects and native Save as](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview),
[Power Query decompression](https://learn.microsoft.com/en-us/powerquery-m/binary-decompress).
