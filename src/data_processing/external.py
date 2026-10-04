"""Replay saved external evidence without making a network or model call."""

import json
from .recovery import assert_preserved

EVIDENCE_COLUMNS = (
    "ClientId",
    "candidate_industry",
    "entity_found",
    "entity_confidence",
    "industry_confidence",
    "verification_level",
    "grounding_sources",
    "error_message",
    "matched_company_name",
    "matched_legal_name",
    "economic_activity",
    "evidence_summary",
)


def evidence_decision(row, industries):
    """Use the same conservative acceptance rule in backtests and final fills.

    A declared confidence is not a probability. Require source metadata, a known
    taxonomy label and no service error, then keep accepted fills below 'high'.
    Sources ground the whole response; they do not independently verify each field.
    """
    if str(row.get("entity_found", "")).lower() != "true":
        return "entity_not_found"
    if row.get("error_message"):
        return "service_error"
    if row.get("candidate_industry") not in industries:
        return "invalid_industry"
    if row.get("entity_confidence") != "high" or row.get("industry_confidence") != "high":
        return "insufficient_confidence"
    if row.get("verification_level") not in {"official_registry", "official_corporate"}:
        return "insufficient_verification"
    sources = row.get("grounding_sources", "")
    try:
        sources = json.loads(sources) if isinstance(sources, str) else sources
    except (ValueError, TypeError):
        return "invalid_sources"
    if (
        not isinstance(sources, list)
        or not sources
        or not all(isinstance(s, str) and s.strip() for s in sources)
    ):
        return "missing_sources"
    return "accepted"


def apply_external(rows, evidence, industries):
    """Join one saved evidence record per currently unresolved client.

    Reject duplicate/stale cache entries instead of silently replaying mixed runs.
    The full evidence stays in the separate audit file, outside reporting measures.
    """
    unresolved = {r["ClientId"] for r in rows if r["fill_method"] == "unresolved"}
    mapping, audit = {}, []
    for source in evidence:
        if not set(EVIDENCE_COLUMNS).issubset(source):
            raise ValueError("Incomplete external evidence schema")
        client = str(source["ClientId"])
        if client in mapping:
            raise ValueError("Duplicate ClientId in external evidence cache")
        if client not in unresolved:
            raise ValueError("External evidence cache contains a stale or already resolved client")
        decision = evidence_decision(source, industries)
        mapping[client] = source if decision == "accepted" else None
        audit.append(dict(source, acceptance_decision=decision))
    result = []
    for source in rows:
        row = dict(source)
        accepted = mapping.get(row["ClientId"]) if row["fill_method"] == "unresolved" else None
        industry = accepted["candidate_industry"] if accepted else row["industry_filled"]
        row.update(
            industry_final=industry or "Unresolved",
            fill_method_final="llm_external" if accepted else row["fill_method"],
            confidence_level="medium_low" if accepted else "unresolved" if not industry else "high",
        )
        result.append(row)
    assert_preserved(rows, result)
    return result, audit
