# Fill Quality Report

## Scope

These counts and monetary totals were recalculated from the supplied reporting
snapshot on 2026-10-04. Historical validation and model results are candidate-
reported until fresh experiment outputs and saved evidence are available. The source
code has now been reviewed; corrected evaluation and acceptance rules require reruns.

| Measure | Result |
| --- | ---: |
| Policy rows / unique policy IDs | 50,441 / 50,441 |
| Unique client IDs | 8,565 |
| Known industry categories | 15 |
| Additional unresolved category | `Unresolved` |
| Initially missing, implied by method flags | 17,631 (34.95%) |
| Recovered rows | 16,275 (92.31% of initially missing) |
| Resolved rows | 49,085 (97.31% of all rows) |
| Unresolved rows | 1,356 (2.69% of all rows) |

## Recovery by method

| `fill_method` | Policies | Portfolio share | `confidence_level` |
| --- | ---: | ---: | --- |
| `original` | 32,810 | 65.05% | `high` |
| `client_id` | 16,159 | 32.04% | `high` |
| `llm_external` | 116 | 0.23% | `medium_low` / `low` |
| `unresolved` | 1,356 | 2.69% | `unresolved` |
| **Total** | **50,441** | **100.00%** | |

Individual rounded shares sum to 100.01%. This is a rounding effect.
`client_id` accounts for 91.65% of initially missing rows. The final CSV contains
`Unresolved`, not the `Pending` label used in the earlier reports.

External enrichment affects **116 policies across 52 clients**: 88 policies / 30
clients at `medium_low`, and 28 policies / 22 clients at `low`.

## Premium by evidence tier

Currency is unspecified in the challenge and CSV. Values below are exact source
amounts; **MXN is an assumption** and no conversion has been applied.

| Tier | Premium amount | Premium share |
| --- | ---: | ---: |
| `high`: original + same-client | 22,817,550,691.32 | 97.24% |
| `medium_low` + `low`: external | 178,918,077.31 | 0.76% |
| `unresolved` | 468,894,004.47 | 2.00% |
| **Total** | **23,465,362,773.10** | **100.00%** |

Resolved industry covers 98.00% of premium, which differs from 97.31% row coverage.
If external candidates are treated as unresolved for sensitivity analysis, known
industry covers 97.08% of rows and 97.24% of premium. Portfolio premium itself is
unchanged.

## Confidence assessment

**Same-client propagation.** The candidate reports zero industry conflicts among
labeled clients and 100% leave-one-out agreement on 29,963 policy rows. The final
snapshot also contains no industry conflicts within a client. That verifies
internal consistency, not independent correctness of source labels. Policies
within a client are correlated; a row-level binomial confidence interval should
not be interpreted as a guarantee of population accuracy.

**External candidates.** The candidate reports a 45-client backtest with 41
abstentions and four candidates, none matching the known portfolio industry.
This small accepted sample does not establish reliable predictive performance.
Retain the current flags, review the 52-client evidence mapping, and expose a
dashboard comparison treating the external layer as unresolved. Confidence tiers
are qualitative provenance labels, not calibrated probabilities.

**Unresolved.** The 1,356 rows remain in the dataset and monetary totals. They are
not dropped or assigned a majority class. ML predictions were reportedly not used
for final fills; reproduction requires original input, saved evidence and execution of the reviewed notebooks.

## Integrity checks performed

- Expected 13-column schema and UTF-8 decoding.
- No blank values in the reporting fields.
- Zero duplicate policy IDs and zero fully duplicated rows.
- All monetary values finite and nonnegative.
- All dates valid; no end date precedes its start date.
- Method/confidence combinations and unresolved labels consistent.
- One reporting name and no conflicting industry per client ID.
- Exact counts, premium total and SHA-256 match the supplied snapshot.

See [validation output](reporting_validation.json) and the
[technical write-up](technical_writeup.md). These controls do not establish raw-
to-final lineage or the correctness of external entity matches.
