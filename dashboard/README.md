# Premium and growth dashboard

The Power BI project has two pages, **Resumen** and **Detalle**, with filters for
industry, state, municipality, coverage and client. It includes Premium/Premium
Growth, a cutoff date, YTD/Last Year comparisons, ranking and policy detail.
The model has 12 tables and 70 measures. Client labels combine ID and name.

## Download and open

Download the **complete repository ZIP** using GitHub's Code → Download ZIP,
or clone it. Extract it into a reasonably short folder path on Windows.
Keep the `.pbip`, `.Report` and `.SemanticModel` together. The small `.pbip` file
alone is a project pointer and does not contain the report, model or data.

From the extracted repository root:

```powershell
python dashboard/setup_dashboard.py
```

This validates the reporting CSV, creates an ignored local copy under `work/pbi/`
and sets its required `ReportingCsvPath` parameter to the CSV's current location.
Open `work/pbi/premium_growth.pbip` in a recent **Power BI Desktop for Windows**,
select **Refresh**, and save after checking the results. Use a new output directory
if configuring again:

```powershell
python dashboard/setup_dashboard.py --output work/pbi_review
```

The shared source project is `dashboard/premium_growth.pbip`. It has a blank required
CSV parameter to avoid publishing personal machine paths. If configuring manually,
open the shared project and set **Transform data → Manage parameters → ReportingCsvPath**
to the absolute path of `data/processed/portfolio_reporting.csv`, then apply/refresh.
Do not commit your personal path. Python is only a setup convenience; it is not
needed when you configure the parameter manually in Desktop.

## Files that must travel together

```text
dashboard/
├── premium_growth.pbip
├── premium_growth.Report/
│   ├── definition.pbir
│   ├── definition/                  Pages, visuals and bookmarks
│   └── StaticResources/             Registered theme and images
├── premium_growth.SemanticModel/
│   ├── definition.pbism
│   └── definition/                  TMDL tables, relationships and CSV parameter
└── setup_dashboard.py
data/processed/portfolio_reporting.csv
```

The report/model links are relative. Graphics and themes are included in the
project; they do not depend on personal image folders. Local cache, personal
settings, unapplied queries and backup folders are excluded. Without a cache,
Desktop loads the model definition before data is refreshed; initial blank visuals
do not by themselves mean the project is broken.

## Checks and remaining risks

- **PASS:** complete JSON dependencies, registered assets, table/field bindings,
  model TMDL deserialization with Microsoft's library and local setup copy.
- **PASS:** reporting data reconciliation against original IDs, dates, amounts,
  original industry labels, same-client assignments and canonical names.
- **Desktop execution pending:** opening, refresh, DAX values, slicer interactions
  and bookmark rendering were not executed in a running Power BI Desktop session.
  See `reports/dashboard_validation.json` and [review notes](../docs/dashboard_review.md).
- The calendar is fixed through 2024. It covers this submission's start dates;
  adding later policies requires extending/reviewing it before refresh.
- YTD cards are cutoff-period values. Compare them against the same period,
  not the four-year portfolio total. Independent year-end controls are in
  `reports/dashboard_control_totals.json`.
- The client concentration selector uses an explicit client ID. Review that rule
  if the input is replaced. Missing prior-year denominators remain blank.
- A PBIX exported **from Desktop after refresh** may be added later for a convenient
  single-file viewer handoff. No PBIX was fabricated from the project files.

GitHub stores the source; it does not run the interactive dashboard in a browser.
A Power BI Service publication is a separate action and was not performed here.

References: [Power BI projects](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview),
[report dependencies](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report),
[cache and semantic model](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset).
