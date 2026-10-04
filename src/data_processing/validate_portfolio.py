"""Validate a reporting CSV without changing it or rerunning industry recovery.

Only Python's standard library is required. Paths come from arguments or the
repository location, so the same entry point can be used locally or on Databricks.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "portfolio_reporting.csv"
DEFAULT_CONTRACT = PROJECT_ROOT / "config" / "portfolio_contract.json"


def validate_portfolio(input_path, contract_path=DEFAULT_CONTRACT, verify_snapshot=False):
    """Return aggregate diagnostics; never expose client identifiers in errors.

    Contract checks assess schema and internal consistency. Snapshot verification
    also compares the exact submitted file, counts and monetary total to the saved
    baseline. Neither check proves the accuracy of an inferred industry label.
    """
    input_path = Path(input_path)
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    expected_fields = contract["columns"]
    issues = Counter()
    samples = defaultdict(list)
    methods = Counter()
    confidence = Counter()
    premium_by_method = defaultdict(Decimal)
    blank_counts = Counter()
    client_industries = defaultdict(set)
    client_names = defaultdict(set)
    clients = set()
    policies = set()
    total_premium = Decimal(0)
    row_count = 0
    unresolved_count = 0

    def record_issue(code, line=None):
        issues[code] += 1
        # Bound the diagnostic payload even when a whole file is malformed.
        if line is not None and len(samples[code]) < 5:
            samples[code].append(line)

    def build_result():
        return {
            "status": "FAIL" if issues else "PASS",
            "scope": "reporting_snapshot" if verify_snapshot else "data_contract",
            "file_name": input_path.name,
            "rows": row_count,
            "unique_clients": len(clients),
            "unique_policies": len(policies),
            "unresolved_rows": unresolved_count,
            "industry_coverage_pct": (
                round(100 * (row_count - unresolved_count) / row_count, 4)
                if row_count else None
            ),
            # Decimal keeps cent-level totals exact, unlike binary floats.
            "premium_total": str(total_premium),
            "premium_by_method": {key: str(value) for key, value in sorted(premium_by_method.items())},
            "method_counts": dict(sorted(methods.items())),
            "confidence_counts": dict(sorted(confidence.items())),
            "blank_counts": {field: blank_counts[field] for field in expected_fields},
            "issues": dict(sorted(issues.items())),
            "example_csv_line_numbers": dict(sorted(samples.items())),
        }

    # utf-8-sig accepts plain UTF-8 and UTF-8 with BOM. newline='' lets csv handle
    # quoted delimiters and embedded line breaks without manual string splitting.
    with input_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_fields:
            record_issue("schema_mismatch")
            return build_result()

        for row in reader:
            row_count += 1
            line = reader.line_num
            if None in row or any(value is None for value in row.values()):
                record_issue("malformed_csv_row", line)
                continue
            for field, value in row.items():
                if not value.strip():
                    blank_counts[field] += 1
                    record_issue("blank_" + field, line)
                if "\ufffd" in value:
                    record_issue("replacement_character", line)

            client = row["ClientId"]
            policy = row["policy_id"]
            if policy in policies:
                record_issue("duplicate_policy_id", line)
            policies.add(policy)
            clients.add(client)
            client_names[client].add(row["client_name"])

            method = row["fill_method"]
            tier = row["confidence_level"]
            industry = row["industry"]
            methods[method] += 1
            confidence[tier] += 1
            allowed_tiers = contract["confidence_by_method"].get(method)
            if allowed_tiers is None:
                record_issue("unknown_fill_method", line)
            elif tier not in allowed_tiers:
                record_issue("inconsistent_method_confidence", line)
            if industry not in contract["industry_labels"]:
                record_issue("unknown_industry", line)
            is_unresolved = industry == contract["unresolved_label"]
            unresolved_count += int(is_unresolved)
            if is_unresolved != (method == "unresolved"):
                record_issue("inconsistent_unresolved_label", line)
            if not is_unresolved:
                client_industries[client].add(industry)

            for field in ("premium", "sum_insured"):
                try:
                    value = Decimal(row[field])
                except InvalidOperation:
                    record_issue("invalid_" + field, line)
                    continue
                if not value.is_finite():
                    record_issue("nonfinite_" + field, line)
                    continue
                if value < 0:
                    record_issue("negative_" + field, line)
                if field == "premium":
                    total_premium += value
                    premium_by_method[method] += value

            parsed_dates = {}
            for field in ("policy_start_date", "policy_end_date"):
                try:
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[field]):
                        raise ValueError("Expected ISO date")
                    parsed_dates[field] = date.fromisoformat(row[field])
                except ValueError:
                    record_issue("invalid_" + field, line)
            if len(parsed_dates) == 2 and parsed_dates["policy_end_date"] < parsed_dates["policy_start_date"]:
                record_issue("end_before_start", line)

    if not row_count:
        record_issue("empty_dataset")
    for industries in client_industries.values():
        if len(industries) > 1:
            record_issue("client_industry_conflict")
    for names in client_names.values():
        if len(names) > 1:
            record_issue("multiple_reporting_names_per_client")

    if verify_snapshot:
        baseline = contract["snapshot"]
        observed = {
            "rows": row_count,
            "unique_clients": len(clients),
            "method_counts": dict(methods),
            "confidence_counts": dict(confidence),
        }
        for key, value in observed.items():
            if value != baseline[key]:
                record_issue("snapshot_mismatch_" + key)
        if total_premium != Decimal(baseline["premium_total"]):
            record_issue("snapshot_mismatch_premium_total")
        # Hash verification intentionally detects byte changes as well as value
        # changes; line-ending conversion is therefore a snapshot mismatch.
        digest = hashlib.sha256()
        with input_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != baseline["sha256"]:
            record_issue("snapshot_mismatch_sha256")

    return build_result()


def main(argv=None):
    """Exit 0 for a valid dataset, 1 for data issues, and 2 for input errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--verify-snapshot", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional JSON diagnostics file")
    args = parser.parse_args(argv)
    try:
        report = validate_portfolio(args.input, args.contract, args.verify_snapshot)
    except (OSError, UnicodeError, csv.Error, ValueError, KeyError, TypeError) as exc:
        # Keep paths and other input details out of logs that may be made public.
        parser.exit(2, f"Cannot validate input ({type(exc).__name__}). Check the CSV and contract.\n")
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        # A mistaken --output must never overwrite the dataset or its contract.
        if args.output.resolve() in {args.input.resolve(), args.contract.resolve()}:
            parser.error("--output must differ from --input and --contract")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
