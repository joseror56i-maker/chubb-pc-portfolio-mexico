"""Canonical display names within a ClientId, preserving the candidate's ranking.

No fuzzy merge of different clients. Match keys remove accents/punctuation/legal
suffixes only for grouping; the display name retains accents and legal spelling.
"""

import re
from collections import defaultdict

LEGAL_SUFFIX = re.compile(r"\s+(S A B|S A|S DE R L|S R L|S C|SAB|SA|SRL|SC)(\s+DE C V)?$")


def clean_name(value):
    value = re.sub(r"[\u200b-\u200d\ufeff]", "", str(value))
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def match_key(name):
    value = name.upper().translate(str.maketrans("ÁÉÍÓÚÜÑ", "AEIOUUN"))
    value = re.sub(r"[^A-Z0-9 ]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return LEGAL_SUFFIX.sub("", value).strip()


def canonical_names(rows):
    """Rank family frequency, richness and first date, then choose a display variant.

    Stable lexical tie breaks make the choice independent of input row ordering.
    A reference policy records where the chosen spelling came from.
    """
    clients = defaultdict(list)
    for row in rows:
        clients[row["ClientId"]].append(row)
    names, lineage = {}, []
    for client, policies in sorted(clients.items()):
        variants = defaultdict(list)
        for row in policies:
            name = clean_name(row["client_name"])
            if name:
                variants[name].append(row)
        if not variants:
            raise ValueError("A client has no usable display name")
        families = defaultdict(list)
        for name in variants:
            families[match_key(name)].append(name)

        def first_date(name):
            return min(r["policy_start_date"] for r in variants[name])

        def family_rank(key):
            members = families[key]
            return (
                -sum(len(variants[n]) for n in members),
                -max(len(n.split()) for n in members),
                -max(len(n) for n in members),
                min(first_date(n) for n in members),
                key,
            )

        family = min(families, key=family_rank)

        def variant_rank(name):
            return (
                -len(name.split()),
                -len(name),
                name == name.upper(),
                -len(variants[name]),
                first_date(name),
                name,
            )

        chosen = min(families[family], key=variant_rank)
        reference = min(variants[chosen], key=lambda r: (r["policy_start_date"], r["policy_id"]))
        names[client] = chosen
        lineage.append(
            {
                "ClientId": client,
                "client_name_reporting": chosen,
                "reference_policy_id": reference["policy_id"],
                "reference_start_date": reference["policy_start_date"],
                "reference_raw_name": reference["client_name"],
                "match_family": family,
                "variant_count": len(variants),
                "family_count": len(families),
            }
        )
    return names, lineage


def build_reporting(rows, columns):
    names, lineage = canonical_names(rows)
    result = []
    for source in rows:
        row = {key: source.get(key, "") for key in columns}
        row.update(
            client_name=names[source["ClientId"]],
            industry=source["industry_final"],
            fill_method=source["fill_method_final"],
        )
        result.append(row)
    return result, lineage
