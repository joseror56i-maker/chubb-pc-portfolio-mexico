# Fill Quality Report
## P&C Portfolio Mexico — Industry Recovery

## Summary

The source portfolio contains **50,441 policies** and **17,631 missing industry values**, equivalent to an initial missing rate of **34.95%**.

The final recovery process increases industry coverage from **65.05% to 97.31%**.

| Fill method | Policies | Share of portfolio | Confidence |
|---|---:|---:|---|
| Original source label | 32,810 | 65.05% | High |
| `ClientId` propagation | 16,159 | 32.04% | High |
| External enrichment | 116 | 0.23% | Medium-low / Low |
| `unresolved` / `Unresolved` | 1,356 | 2.69% | Unresolved |
| **Total** | **50,441** | **100.00%** | |

Of the **17,631 originally missing records**, **16,275 were recovered**, equivalent to **92.31% of the missing population**.

---

## Recovery by Method

### ClientId propagation

Recovered:

**16,159 policies**

This represents:

**91.65% of all originally missing industry values**

### Confidence: High

This method uses direct same-client evidence and was validated before use.

Key validation results:

- **0** observed industry conflicts among labeled `ClientId`s;
- **29,963** leave-one-out validation rows;
- **100%** leave-one-out accuracy;
- real recovery coverage was consistent with simulated missingness.

The full validation design and rationale are documented in the technical write-up.

---

### External enrichment

Recovered:

**116 policies across 52 clients**

| Confidence | Policies | Clients |
|---|---:|---:|
| Medium-low | 88 | 30 |
| Low | 28 | 22 |

### Confidence: Medium-low / Low

External classifications were accepted only as a secondary source and were never allowed to overwrite original or `ClientId`-derived labels.

A backtest showed weak agreement between external real-world classification and the labels contained in the portfolio, so these fills are explicitly kept in lower confidence tiers.

---

## Remaining Unresolved

After all recovery stages:

**1,356 policies remain unresolved**

This corresponds to:

**2.69% of the portfolio**

These records are retained as:

```text
Unresolved
```

They are not dropped, assigned to the majority class or filled with weak model predictions.

### Confidence: Unresolved

The available evidence was insufficient to support a defensible industry assignment.

---

## Premium Exposure by Confidence

Currency is not specified in the source. The amounts below preserve the original units without conversion; MXN is only an assumption.

| Confidence tier | Premium in source units | Share of premium |
|---|---:|---:|
| High — original + `ClientId` | 22,817,550,691.32 (~22.818B) | 97.24% |
| Medium-low / Low — external | 178,918,077.31 (~178.9M) | 0.76% |
| Unresolved | 468,894,004.47 (~468.9M) | 2.00% |
| **Total** | **23,465,362,773.10 (~23.465B)** | **100.00%** |

Approximately **98.00% of total portfolio premium** has an industry assignment in the final reporting layer.

---

## Quality Conclusion

The final strategy favors reliability over forced completeness.

- The overwhelming majority of recovered rows come from validated same-client evidence.
- External enrichment contributes only a small, explicitly lower-confidence layer.
- Residual uncertainty remains visible as `Unresolved`.

For the full analytical validation — including missingness analysis, leakage controls, ML benchmarks, text models, clustering, external backtesting and concentration checks — see:

[full technical write-up](technical_writeup.md)

---

## Decision Rationale and Limits

### Why original labels were preserved

The task is to recover missing values, not to replace the supplied taxonomy.
Original labels remain the first evidence tier. Their high flag indicates source
provenance; it does not claim an independent audit of every client's real-world activity.

### Why same-client propagation was prioritized

A known industry for the same ClientId is direct internal evidence. Zero observed
label conflicts supports one unique industry mapping per client, so the join must
not multiply policies. Names are display values: exact names can belong to distinct
IDs and do not justify merging identities. Propagation is limited to missing rows.

The 29,963-row leave-one-out test assesses recoverability from other labeled policies
of the same client. It demonstrates consistency in that eligible population;
it does not establish unseen-client prediction accuracy or independent correctness
of the original taxonomy. The real/simulated missingness comparison supports the
coverage interpretation, not a claim that every missingness mechanism is random.

### Why ML predictions were excluded

Client-level validation reduces leakage and repeated-client weighting. Basic
categorical rules, boosted multiclass models, name-text models, clustering and
one-vs-rest checks did not demonstrate enough generalizable signal. Accepting
their predictions would increase apparent coverage without reliable evidence.
The full technical write-up preserves the features, baseline comparisons,
model metrics, alternative tests and reasoning behind this production decision.

### Why external results remain lower confidence

External research separates entity identification, economic activity and taxonomy
mapping. A generic name is not sufficient identity evidence. The historical
backtest evaluated 45 known clients: 41 abstentions and four classifications,
with zero matching the portfolio industry. This does not validate external accuracy.

The final 52-client / 116-policy external contribution is preserved and flagged.
It requires an auditable record of source URLs, matched identity, activity,
taxonomy decision and uncertainty. The corrected replay workflow uses a reviewed
evidence cache and conservative acceptance controls; historical fills are not
presented as newly reproduced results of that revised workflow.

### Why abstention is preferable to forced completeness

The remaining 1,356 policies have industry = Unresolved, fill_method = unresolved
and confidence_level = unresolved. A majority label, a weak prediction or a name-only
guess would hide uncertainty. Dropping policies would also change the portfolio
denominator and premium. Retaining them preserves full portfolio exposure.

## Confidence Interpretation and Sensitivity

Confidence levels are qualitative evidence tiers, not calibrated probabilities.
Row coverage and premium coverage answer different questions: 97.31% of policies
and 98.00% of premium have an industry assignment. External fills represent 0.23%
of policies and 0.76% of premium. A sensitivity treating external assignments as
unresolved leaves all portfolio counts and total premium unchanged; internal
source/same-client evidence then covers 97.24% of premium.

## Data Integrity Checks

- 50,441 rows and unique policy IDs; 8,565 ClientIds; 13 reporting columns.
- No duplicated policy IDs or fully duplicated rows.
- Valid dates, finite nonnegative monetary values and consistent method/confidence flags.
- Original-to-reporting preservation of identity, amounts, dates and source industries.
- Same-client fills and observed canonical client names reconciled against the original.
- Exact source premium total: 23,465,362,773.10; CSV fingerprint preserved.
- Research metrics retain their historical scope. New execution is needed to
  claim reproduction after changes to validation or external acceptance logic.

These checks support data preservation and internal consistency. They do not
independently certify external identity matches or the real-world accuracy of labels.
