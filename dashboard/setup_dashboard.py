"""Configure an ignored local Power BI copy without changing the shared project."""

import argparse
import shutil
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_processing.validate_portfolio import validate_portfolio


def prepare_dashboard(data_path, output_dir, source_dir=None):
    """Validate the CSV, copy every project dependency and set its data parameter.

    The required source parameter is intentionally blank in Git. Absolute file
    paths belong only to this ignored copy, so a clone can be configured anywhere.
    """
    source = Path(source_dir or ROOT / "dashboard").resolve()
    output = Path(output_dir).resolve()
    data = Path(data_path).resolve()
    if output == source or source in output.parents:
        raise ValueError("Choose an output directory outside the shared dashboard folder")
    if output.exists():
        raise ValueError("Output already exists; choose a fresh local dashboard directory")
    validation = validate_portfolio(data, ROOT / "config/portfolio_contract.json")
    if validation["status"] != "PASS":
        raise ValueError("Reporting CSV failed validation; fix the data before configuring Power BI")
    names = ("premium_growth.pbip", "premium_growth.Report", "premium_growth.SemanticModel")
    if any(not (source / name).exists() for name in names):
        raise ValueError("Download the complete repository; required project dependencies are missing")
    for name in names:
        target = output / name
        for item in ([source / name] if (source / name).is_file() else (source / name).rglob("*")):
            relative = item.relative_to(source)
            if len(str(output / relative)) >= 260:
                raise ValueError("Use a shorter output directory for Power BI Desktop's Windows path limit")
    output.mkdir(parents=True)
    shutil.copyfile(source / names[0], output / names[0])
    for name in names[1:]:
        shutil.copytree(source / name, output / name)
    expression = output / "premium_growth.SemanticModel/definition/expressions.tmdl"
    # M escapes a quote by doubling it; forward slashes work in Windows file paths.
    literal = data.as_posix().replace('"', '""')
    expression.write_text(
        f'expression ReportingCsvPath = "{literal}" meta '
        '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n',
        encoding="utf-8", newline="\n",
    )
    return output / "premium_growth.pbip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed/portfolio_reporting.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "work/pbi")
    args = parser.parse_args()
    try:
        project = prepare_dashboard(args.data, args.output)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Dashboard setup stopped: {error}\n")
    print(f"Open in Power BI Desktop, then Refresh: {project}")


if __name__ == "__main__":
    main()
