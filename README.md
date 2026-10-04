# Mexico P&C Portfolio: Industry Recovery and Premium Growth

Repository: [joseror56i-maker/chubb-pc-portfolio-mexico](https://github.com/joseror56i-maker/chubb-pc-portfolio-mexico).

A technical challenge solution for a Mexican Property & Casualty portfolio.
The supplied reporting snapshot contains **50,441 policies** and **8,565 clients**.
Industry is assigned for **97.31% of policy rows**. The remaining **1,356 rows**
are explicitly labeled `Unresolved` and remain in portfolio totals.

The approach prioritizes same-client evidence, tests whether models generalize to
unseen clients, and retains uncertainty when the evidence is insufficient.

## Submission status

| Deliverable | Current status |
| --- | --- |
| GitHub repository | Initial packaging stage; processing, modeling and dashboard areas are separated |
| README | Available with setup, assumptions and honest execution limits |
| Filled dataset | `data/processed/portfolio_reporting.csv`; supplied snapshot, renamed without changing its bytes |
| Fill quality report | Available and reconciled against the reporting CSV |
| Interactive dashboard | Awaiting the candidate's Power BI file and preview |
| Short write-up | Available; detailed analytical notes retained in an appendix |

**The original recovery and modeling source has not yet been supplied.** The
validation script and notebook in this package are new quality controls, not a
replacement for that source. They validate the final CSV; they do not reproduce
the fill process, the reported modeling experiments, or the dashboard.

## Results

| Method (`fill_method`) | Policies | Confidence label |
| --- | ---: | --- |
| `original` | 32,810 | `high` |
| `client_id` | 16,159 | `high` |
| `llm_external` | 116 | `medium_low` / `low` |
| `unresolved` | 1,356 | `unresolved` |
| **Total** | **50,441** | |

The method counts imply 17,631 initially missing rows and 16,275 recovered rows
(92.31% of the originally missing population). That reconciliation assumes the
supplied method flags accurately preserve provenance. Original-value preservation
cannot be independently checked until the raw input and pipeline are available.

See the [fill quality report](reports/fill_quality_report.md),
[short write-up](reports/technical_writeup.md), and
[detailed appendix](reports/technical_appendix.md).

## Repository layout

```text
chubb-pc-portfolio-mexico/
├── README.md
├── requirements.txt
├── .python-version
├── .gitignore
├── .gitattributes
├── .github/workflows/quality-checks.yml
├── config/
│   └── portfolio_contract.json
├── data/
│   ├── raw/README.md
│   └── processed/portfolio_reporting.csv
├── src/
│   ├── data_processing/validate_portfolio.py
│   └── modeling/README.md
├── notebooks/
│   ├── README.md
│   └── 00_validate_reporting_dataset.ipynb
├── tests/
│   └── test_validate_portfolio.py
├── reports/
│   ├── fill_quality_report.md
│   ├── technical_writeup.md
│   ├── technical_appendix.md
│   └── reporting_validation.json
├── docs/
│   ├── data_dictionary.md
│   ├── runbook.md
│   ├── review_notes.md
│   └── submission_checklist.md
├── dashboard/README.md
└── assets/README.md
```

## Run locally with Python / Visual Studio Code

The available validator uses only the Python standard library and was tested with
**Python 3.12.14**. No pip packages are needed for this stage. Open the repository
folder in Visual Studio Code and select your Python interpreter.

From the repository root:

```powershell
python src/data_processing/validate_portfolio.py --verify-snapshot --output work/quality_check.json
python -m unittest discover -s tests -v
```

The command exits with `0` for a valid file, `1` for failed data checks, and `2` for
an unreadable input or invalid arguments. `--verify-snapshot` checks the exact
submitted bytes and baseline totals. For another portfolio, use an explicit input
and omit that flag; update the contract deliberately for a new taxonomy.

```powershell
python src/data_processing/validate_portfolio.py --input "path/to/portfolio.csv" --contract config/portfolio_contract.json
```

GitHub Actions runs the same tests and snapshot checks on pushes and pull requests.

The source CSV is never modified. Generated diagnostics contain aggregate counts
and CSV line numbers, not client identifiers.

## Run on Databricks

Open this repository in a Databricks Git folder and use
`notebooks/00_validate_reporting_dataset.ipynb`. It searches the notebook's working
directory and parents for the project contract. The bundled reporting CSV can be
validated from the checked-out folder; a Unity Catalog Volume path can be supplied
as an alternative input.

This is a standard Python validation for the 8.24 MiB snapshot. It runs on the
driver and is not a distributed Spark recovery job. Execution on an actual
Databricks workspace is still pending. See the [runbook](docs/runbook.md).

## Analytical decisions and limits

- `ClientId` is the identity key; `client_name` is display text. In this snapshot,
  2,310 exact display names are shared by multiple client IDs. Never join or count
  clients by name alone.
- The source reports describe no sufficient unseen-client predictive signal.
  Model predictions were reportedly excluded from the final industry field.
  Those experiments still need their source, seeds, splits and dependencies.
- External enrichment is a low-confidence candidate layer. The reported backtest
  had zero matches among four accepted candidates (45 clients evaluated). Its
  correctness is not established; review its evidence and show sensitivity with
  these 116 rows treated as unresolved.
- `high`, `medium_low` and `low` are provenance tiers, not calibrated probabilities.
- Currency is not specified by the challenge or a CSV column. **MXN is the
  candidate's assumption**, not independently verified metadata. No USD conversion
  has been established.
- A dominant client accounts for 10,189 policies and 18.41% of premium. Keep it in
  official totals and offer a clearly labeled concentration sensitivity view.
- Use policy start date as the proposed written-premium time basis, subject to
  confirmation in the Power BI model. Start dates span 2021-2024; end dates extend
  to 2026. Growth must compare equivalent periods and handle absent prior-year
  values explicitly.

## Dashboard

The Power BI file has not yet been supplied. Intended outputs are Premium and
Premium Growth over time, filterable by industry and location. Coverage and client
filters may extend the required views. No DAX measure or connection has been
validated at this stage.

See [dashboard packaging and refresh requirements](dashboard/README.md). Add the
actual preview to `assets/dashboard_preview.png` and the reviewed downloadable file
to `dashboard/premium_growth_dashboard.pbix` when available.

## Data provenance and publication

The processed file was supplied as
`Client_Name_Normalization_Reporting_FINAL_v2.csv` and copied under the shorter
name `portfolio_reporting.csv`. Column names, values, row order, encoding and
bytes are unchanged. The snapshot fingerprint is in
`config/portfolio_contract.json`.

The challenge requests a public repository. Publication must account for the
dataset's client identifiers, client names and policy amounts, as well as any data
embedded in a PBIX. No open-source or data license has been assumed. This project
is a candidate submission and is not an official Chubb product.

## Review and remaining work

The [review notes](docs/review_notes.md) explain the documentation corrections and
unverified claims. The [submission checklist](docs/submission_checklist.md) maps
the six deliverables to the remaining work. The original raw input, notebooks,
external-evidence mapping and Power BI file are needed to complete reproducibility
and the end-to-end review.
