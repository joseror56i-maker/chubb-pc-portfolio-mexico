"""Candidate's company-resolution prompt and typed schema, extracted from source."""

import json
from pathlib import Path

INDUSTRIES = [
    label
    for label in json.loads(
        (Path(__file__).resolve().parents[2] / "config/portfolio_contract.json").read_text(
            encoding="utf-8"
        )
    )["industry_labels"]
    if label != "Unresolved"
]

enrichment_schema = {
    "entity_found": {
        "type": "boolean",
        "description": "True only if a real company or organization can be reliably identified.",
    },
    "matched_company_name": {
        "type": "string",
        "description": "Most appropriate publicly recognized name of the identified organization.",
    },
    "legal_name": {
        "type": "string",
        "description": "Verified legal or registered company name when available.",
    },
    "economic_activity": {
        "type": "string",
        "description": "Principal economic activity supported by retrieved external evidence.",
    },
    "industry": {
        "type": "enum",
        "labels": INDUSTRIES,
        "description": "Industry that best represents the verified principal economic activity. "
        "Return null when no category is sufficiently supported.",
    },
    "entity_confidence": {
        "type": "enum",
        "labels": ["high", "medium", "low", "unresolved"],
        "description": "Confidence in the real-world entity resolution.",
    },
    "industry_confidence": {
        "type": "enum",
        "labels": ["high", "medium", "low", "unresolved"],
        "description": "Confidence in the mapping from verified economic activity to industry.",
    },
    "verification_level": {
        "type": "enum",
        "labels": ["official_registry", "official_corporate", "reliable_secondary", "insufficient"],
        "description": "Strongest type of retrieved evidence supporting the entity.",
    },
    "evidence_summary": {
        "type": "string",
        "description": "Brief summary of the external evidence supporting the entity and its activity.",
    },
}

instructions = """
Perform company entity resolution and industry classification for a
Mexican commercial insurance portfolio.

The input contains:
- one or more company-name variants for the same ClientId
- state information
- municipality information

Use web search to investigate whether the input corresponds to a real
company or organization operating in Mexico.

IMPORTANT:
Company names may appear as acronyms, trade names, abbreviated names,
legal names, or spelling variations.

Examples:
- PEMEX can correspond to Petróleos Mexicanos.
- CEMEX SAB can correspond to CEMEX S.A.B. de C.V.
- Grupo Bimbo S.A. de C.V. can correspond to Grupo Bimbo.

State and municipality are contextual clues only.
They may represent the insured location and do NOT need to match the
company headquarters exactly.


STAGE 1 — IDENTIFY THE ENTITY

Search for the organization using the available company-name variants.

Prefer these sources when available:

1. Mexican government or regulatory sources.
2. Stock-exchange or official corporate filings.
3. Official company websites.
4. Reputable business or institutional sources.

Use aliases, acronyms and legal-name variations when resolving the entity.

Do NOT reject a match only because:
- punctuation differs
- accents differ
- legal suffixes differ
- the input uses an acronym or trade name
- state or municipality differs from headquarters

Return entity_found = true when the available evidence reasonably and
unambiguously identifies a real organization.

Return entity_found = false when:
- no credible real organization can be found
- the name is too generic
- multiple unrelated organizations are equally plausible
- the match would require guessing

Do NOT infer identity only from how the company name sounds.


STAGE 2 — ECONOMIC ACTIVITY

Only if entity_found = true:

Determine the principal economic activity of the identified organization.

Base this on information about what the organization actually does.

Do NOT infer the activity from keywords in the input name.

Examples:
- "Constructora ABC" is not automatically Construcción.
- "Transportes XYZ" is not automatically Transporte y Logística.
- "Tecnologías ABC" is not automatically Tecnología.

For diversified groups, use the principal or core activity of the entity
that was actually matched.


STAGE 3 — INDUSTRY MAPPING

Map the verified principal economic activity to ONE of the industries
provided in the output schema.

Choose the category that best represents the principal activity.

If the real entity is identified but its activity cannot reasonably be
mapped to one category:

- industry = null
- industry_confidence = "unresolved"

Do not force a classification.


CONFIDENCE

entity_confidence:

- high:
  the organization is clearly identifiable and there is little meaningful
  ambiguity about the entity.

- medium:
  a likely entity was found but some ambiguity remains.

- low:
  the match is plausible but weak.

- unresolved:
  there is not enough information to identify the entity reliably.


industry_confidence:

- high:
  the principal economic activity maps clearly to one industry.

- medium:
  the mapping is reasonable but the company has meaningful activity across
  more than one category.

- low:
  the mapping is weak.

- unresolved:
  no defensible category can be selected.


VERIFICATION LEVEL

Use:

- official_registry:
  government, regulator, stock exchange or equivalent official record.

- official_corporate:
  official company website or corporate documentation.

- reliable_secondary:
  reputable institutional or business source.

- insufficient:
  identity could not be established reliably.


GENERAL RULES

Do not fabricate legal names, aliases, activities or evidence.

Prefer abstaining over guessing for generic or synthetic-looking company
names.

However, do NOT require absolute certainty.
Well-established organizations such as PEMEX, CEMEX or Grupo Bimbo should
be identifiable when the available evidence clearly points to those
entities.
"""
