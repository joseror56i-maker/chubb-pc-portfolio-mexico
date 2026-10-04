# Short Technical Write-Up

## Objective and outcome

The challenge requires industry recovery before a dashboard can reliably compare
premium and premium growth by industry and location. The supplied final snapshot
contains 50,441 policies and 8,565 client IDs. Of 17,631 initially missing industry
values implied by the method flags, 16,275 were recovered. Industry coverage is
97.31% of rows. The remaining 1,356 rows are explicitly `Unresolved` and stay in
portfolio totals.

Snapshot counts and integrity checks were independently recalculated for this
package. Historical experiments below are reported by the candidate; their
notebooks have been reviewed, and original-to-reporting lineage is verified. Evaluation/acceptance corrections require a fresh run. Details are preserved in the
[appendix](technical_appendix.md).

## Internal evidence first

The same client can have several policies, some labeled and some missing an
industry. The candidate first checked consistency within `ClientId` and reported
zero conflicts among the 7,394 labeled clients. Propagating a known industry within
the same identity recovered 16,159 policies, or 91.65% of originally missing rows.

The reported leave-one-out exercise hid labeled policy rows and recovered them
from other labeled policies of the same client. Agreement was 100% over 29,963
eligible rows. This supports internal consistency of the rule. It does not test
unseen-client inference or independently verify the source taxonomy. Rows within
a client are dependent, so a row-level confidence interval has limited meaning.

## ML feasibility and entity-level validation

The candidate modeled one observation per client to prevent a repeatedly insured
entity from dominating train and validation samples. Features included policy
counts, premium and sum-insured aggregates, durations, geography, and coverage mix.
The prediction question was whether a previously unseen client's industry could
be inferred from available portfolio attributes.

Reported gradient-boosting benchmarks, simpler baselines, name-text models,
clustering and binary tests did not show sufficient out-of-sample signal. The
reported strongest multiclass benchmark achieved 6.80% balanced accuracy versus
6.67% for an equal-class random reference across 15 industries. Accuracy and
balanced accuracy should be compared with their corresponding baselines, using
the same folds and class weighting.

The candidate therefore reports excluding ML predictions from final fills. This
decision should be reproduced with client-safe splits, preprocessing fitted only
on training folds, random seeds, dependency versions and saved benchmark outputs.

## External enrichment and explicit abstention

External candidate classifications contributed 116 policies across 52 clients,
with 88 rows labeled `medium_low` and 28 labeled `low`. They did not overwrite
original or same-client labels, according to the reported design.

The external backtest is a material limitation: among 45 known clients, 41 cases
were abstentions and all four candidate classifications disagreed with the source
industry. This does not establish the external method's accuracy. The portfolio's
taxonomy may differ from public company activity, but that explanation remains
an inference. The accepted 52-client mapping needs traceable sources, match
decisions and review. A sensitivity view should treat all external candidates as
unresolved while keeping total premium unchanged.

The 1,356 remaining rows use `industry = Unresolved`, `fill_method = unresolved`
and `confidence_level = unresolved`. No unsupported replacement or row removal is
required to achieve a complete portfolio view.

## Reporting and business interpretation

`ClientId` is the identity key; names are display values. Name normalization was
reported to choose observed variants without inventing semantic business terms.
In the snapshot, 2,310 exact display names are shared by different client IDs.
Aggregation or joins by name alone would combine distinct entities.

The largest client has 10,189 policies and contributes 18.41% of premium. Unique
policy IDs support retaining the records, while the original input is still
needed to verify lineage and join behavior. Official totals should retain the
client and a separate sensitivity view can explain concentration effects.

The proposed time basis for written premium is policy start date, with complete
start-date years 2021-2024. End dates extend to 2026 and should not accidentally
define the growth calendar. Currency is not specified: MXN is an assumption and
USD measure names would require documented conversion. The Power BI model and
the project definition and DAX source have been reviewed locally. Desktop execution
and refresh validation are still pending.

## Further work

Complete original-data execution and raw-to-final reconciliation, audit external evidence,
and validate Power BI connections, date relationships, totals and growth
denominators after download. With richer client identifiers, verified business
attributes or SCIAN/NAICS mappings, rerun the same unseen-client benchmark rather
than relying on more tuning of weak features.
