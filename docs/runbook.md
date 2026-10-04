# Execution Runbook

## Available execution

The current package validates the supplied reporting CSV. The original recovery
pipeline, modeling notebooks and dashboard are still required for full execution.
Python 3.12.14 was used locally; the validator has no third-party dependencies.

## Visual Studio Code on Windows

1. Extract the delivery ZIP and open the `chubb-pc-portfolio-mexico` folder.
2. Select your Python 3.12 interpreter in Visual Studio Code.
3. Open a terminal at the repository root.
4. Run the commands below. No machine-specific path is embedded in the source.

```powershell
python src/data_processing/validate_portfolio.py --verify-snapshot --output work/quality_check.json
python -m unittest discover -s tests -v
```

You may create a virtual environment with `python -m venv .venv` if desired.
Installing `requirements.txt` currently installs no packages. Modeling libraries
will be pinned from the actual environment after the original code is reviewed.

For a CSV elsewhere, pass its location rather than editing source code:

```powershell
python src/data_processing/validate_portfolio.py --input "D:/challenge/portfolio_reporting.csv" --verify-snapshot
```

Remove `--verify-snapshot` when validating a different snapshot. It checks exact
bytes, counts and premium; even a newline conversion intentionally fails the hash.
`--output` writes a diagnostic JSON and refuses to overwrite the input or contract.

## Databricks

1. Add the GitHub repository as a Databricks Git folder.
2. Open `notebooks/00_validate_reporting_dataset.ipynb`.
3. Run on a compatible Python runtime. The first cell locates the contract by
   searching the working directory and its parents.
4. Leave `INPUT_PATH = None` to validate the bundled CSV. Alternatively, set it
   explicitly to a readable Unity Catalog Volume file path:

```python
INPUT_PATH = "/Volumes/<catalog>/<schema>/<volume>/portfolio_reporting.csv"
```

Replace the bracketed parts with your own location. Access permissions and the
compute environment must allow reading that Volume. A `dbfs:/...` URI is not a
normal Python `Path`; do not pass it to this standard-library validator.

The notebook calls the same Python function as the CLI and raises an exception
if checks fail. For this 8.24 MiB file, validation runs on the driver. It is not
intended as a distributed Spark implementation for large portfolios.

Databricks execution has not yet been tested in a live workspace. The original
pipeline must later be reviewed for explicit schemas, safe joins, overwrite
behavior, client-safe model splits and environment pinning.

## Original pipeline integration

Use this sequence once the original notebooks are supplied:

1. Load raw input with an explicit schema and immutable original labels.
2. Validate client identity and conflicting source industries.
3. Apply deterministic same-client recovery without changing existing labels.
4. Run client-level ML feasibility experiments with isolated training folds.
5. Apply reviewed external mappings only to eligible unresolved clients.
6. Build reporting names and final fields; reconcile row counts and premium.
7. Export the canonical reporting CSV and run the validator.
8. Refresh and reconcile the Power BI model.

This describes the integration plan. It does not claim those missing stages exist.

## References

- [Databricks Git folders](https://docs.databricks.com/aws/en/repos/)
- [Files in Unity Catalog Volumes](https://docs.databricks.com/aws/en/volumes/volume-files)
- [Recommendations for code and data files](https://docs.databricks.com/aws/en/files/files-recommendations)
