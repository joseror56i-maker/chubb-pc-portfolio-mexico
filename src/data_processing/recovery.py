"""Recover industry using evidence belonging to the same ClientId.

The core uses ordinary row dictionaries so it runs in VS Code without Spark,
and in Databricks through the small runtime adapter. Never merge clients by name.
"""

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from datetime import date, datetime

RAW_COLUMNS = (
    "ClientId",
    "policy_id",
    "client_name",
    "state",
    "municipality",
    "coverage_type",
    "industry",
    "premium",
    "sum_insured",
    "policy_start_date",
    "policy_end_date",
)


def parse_date(value):
    """Accept ISO or the candidate's original day/month/year input format."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value = str(value or "").strip()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return datetime.strptime(value, "%d/%m/%Y").date().isoformat()


def prepare_raw(rows, industry_labels):
    """Validate raw inputs before any join; retain IDs as strings and money exactly.

    A reporting export is not raw input: it has overwritten the original industry
    and cannot prove which labels were originally missing. Refuse that shortcut.
    """
    prepared, policies = [], set()
    forbidden = {"fill_method", "confidence_level", "industry_final", "industry_filled"}
    for line, source in enumerate(rows, 2):
        if forbidden.intersection(source):
            raise ValueError("Use the original portfolio, not a filled/reporting export")
        if not set(RAW_COLUMNS).issubset(source) or None in source:
            raise ValueError(f"Invalid raw schema at row {line}")
        row = {key: str(source[key]) if source[key] is not None else "" for key in RAW_COLUMNS}
        for key in (
            "ClientId",
            "policy_id",
            "client_name",
            "state",
            "municipality",
            "coverage_type",
        ):
            if not row[key].strip():
                raise ValueError(f"Missing {key} at row {line}")
        if row["policy_id"] in policies:
            raise ValueError(f"Duplicate policy_id at row {line}")
        policies.add(row["policy_id"])
        row["industry"] = row["industry"].strip()
        if row["industry"] and row["industry"] not in industry_labels:
            raise ValueError(f"Unknown original industry at row {line}")
        for key in ("premium", "sum_insured"):
            try:
                amount = Decimal(row[key])
            except InvalidOperation as error:
                raise ValueError(f"Invalid {key} at row {line}") from error
            if not amount.is_finite() or amount < 0:
                raise ValueError(f"Invalid {key} at row {line}")
        for key in ("policy_start_date", "policy_end_date"):
            row[key] = parse_date(row[key])
        if row["policy_end_date"] < row["policy_start_date"]:
            raise ValueError(f"End date precedes start date at row {line}")
        prepared.append(row)
    if not prepared:
        raise ValueError("The original portfolio is empty")
    return prepared


def recover_by_client(rows):
    """Create exactly one mapping per client, failing on contradictory originals.

    The original notebooks inspected conflicts but joined an unrestricted mapping.
    Rejecting conflicts prevents row multiplication and arbitrary industry choices.
    Existing labels are never overwritten; new labels receive explicit provenance.
    """
    labels = defaultdict(set)
    for row in rows:
        if row["industry"]:
            labels[row["ClientId"]].add(row["industry"])
    if any(len(values) > 1 for values in labels.values()):
        raise ValueError(
            "Conflicting original industries within a ClientId; resolve before recovery"
        )
    mapping = {client: next(iter(values)) for client, values in labels.items()}
    result = []
    for source in rows:
        row = dict(source)
        original = row["industry"]
        filled = original or mapping.get(row["ClientId"], "")
        row.update(
            industry_filled=filled,
            fill_method="original" if original else "client_id" if filled else "unresolved",
        )
        result.append(row)
    assert_preserved(rows, result)
    return result


def assert_preserved(before, after):
    """Check row order, identity, source labels and exact monetary conservation."""
    if len(before) != len(after):
        raise ValueError("A processing step changed the policy count")
    for left, right in zip(before, after):
        for key in RAW_COLUMNS:
            if left[key] != right[key]:
                raise ValueError(f"A processing step changed original {key}")


def describe_portfolio(rows):
    """Return aggregate EDA and leave-one-observation-out recovery coverage.

    LOO concerns known rows of existing clients. It is not validation on unseen
    clients and does not prove the labels of wholly unlabeled clients are correct.
    """
    known_by_client = Counter(row["ClientId"] for row in rows if row["industry"])
    industries_by_client = defaultdict(set)
    for row in rows:
        if row["industry"]:
            industries_by_client[row["ClientId"]].add(row["industry"])
    known = sum(known_by_client.values())
    evaluable = sum(count for count in known_by_client.values() if count > 1)
    return {
        "rows": len(rows),
        "clients": len({r["ClientId"] for r in rows}),
        "premium_total": str(sum((Decimal(r["premium"]) for r in rows), Decimal(0))),
        "missing_original_industry": sum(not r["industry"] for r in rows),
        "clients_with_conflicting_original_industries": sum(
            len(values) > 1 for values in industries_by_client.values()
        ),
        "policies_by_start_year": dict(
            sorted(Counter(r["policy_start_date"][:4] for r in rows).items())
        ),
        "policies_by_state": dict(sorted(Counter(r["state"] for r in rows).items())),
        "original_industry_counts": dict(
            sorted(Counter(r["industry"] or "Unresolved" for r in rows).items())
        ),
        "same_client_loo_known_rows": known,
        "same_client_loo_evaluable_rows": evaluable,
        "same_client_loo_scope": "coverage only; consistency checked during recovery, no unseen-client accuracy claim",
    }
