# Detailed Technical Appendix
## P&C Portfolio Mexico — Industry Recovery & Premium Growth Dashboard

> Historical candidate narrative: the supplied source has been reviewed and corrected,
> but the following experiment results have not been regenerated. See the code
> review for changes to splits and external acceptance.

## 1. Objective

The project had two connected objectives:

1. resolve a major data-quality issue in the `industry` field; and
2. build an interactive business-facing dashboard for **Premium** and **Premium Growth**.

The source portfolio contains **50,441 policy records**. Approximately **35% of the original `industry` values were missing**, which meant that any direct industry-level dashboard would have produced distorted segment comparisons and growth trends.

I therefore treated the industry problem as the core analytical risk and built the solution around a hierarchy of evidence rather than around a single prediction model.

The final reporting dataset preserves all 50,441 policies and reaches **97.31% industry coverage**, while the remaining **2.69%** is kept explicitly as `Unresolved`.


> Evidence scope: the following analytical experiments are candidate-reported and
> have not been rerun. Snapshot checks are documented in `fill_quality_report.md`.
> The unresolved label has been aligned to the actual CSV. MXN is an assumption.
> The row-level Wilson interval does not account for within-client dependence.
> The external backtest does not establish reliable external-fill accuracy.

---

## 2. Initial Data Assessment

### 2.1 Portfolio structure

The portfolio contains:

- **50,441** policies;
- **8,565** unique `ClientId`s;
- **15** industry classes;
- **22** states;
- **109** municipalities;
- policy years from **2021 to 2024**.

Initial missing industry:

- **17,631** policies;
- **34.95%** of the portfolio.

The first important observation was that the same client appears multiple times across the portfolio. This created a potentially very strong deterministic source of information.

### 2.2 Missingness pattern

Missingness was tested across the available dimensions.

#### Year

Industry missingness remained very stable across years:

| Year | Missing rate |
|---|---:|
| 2021 | 35.19% |
| 2022 | 34.87% |
| 2023 | 34.69% |
| 2024 | 35.07% |

The association between year and missingness was effectively negligible.

#### Geography

State and municipality also showed no meaningful concentration of missingness once portfolio size was taken into account.

Large states contained more missing rows mainly because they contained more policies.

#### Coverage type

Coverage type was the one variable clearly associated with the probability that `industry` was missing.

For example:

- Flotilla Vehicular: ~50.6% missing;
- Misceláneos: ~48.2%;
- Ingeniería: ~23.2%;
- Incendio y Terremoto: ~24.6%.

The missingness association was material, but this did **not** imply that coverage type was useful for predicting the missing industry itself.

That distinction became important later.

---

## 3. Deterministic Recovery Using ClientId

### 3.1 Why ClientId came first

The same insured client can hold several policies.

If one record for a `ClientId` contains a known industry while another record for the same client is missing the label, the known record provides direct entity-level evidence.

Before using this rule, I tested whether clients had internally consistent labels.

### 3.2 Label consistency

Among labeled clients:

- **7,394** `ClientId`s had at least one known industry;
- **4,547** had two or more labeled rows;
- **2,847** had only one labeled row;
- **0** labeled clients had conflicting industries.

This meant that no arbitrary majority-vote or conflict-resolution logic was required.

### 3.3 Leave-one-out validation

To test the rule rather than simply assume it was correct, I performed leave-one-out validation.

For each labeled policy belonging to a client with additional labeled policies:

1. hide the policy's industry;
2. infer industry from the remaining rows of the same `ClientId`;
3. compare the inferred value with the hidden true label.

Results:

- **29,963** rows evaluated;
- propagation coverage: **100%**;
- accuracy: **100%**;
- approximate 95% Wilson confidence interval: **99.99%–100%**.

This provided very strong evidence that same-client propagation was a defensible high-confidence fill rule.

### 3.4 Missingness simulation

I also compared real recovery coverage against a simulated random-null process.

- Real ClientId recovery coverage: **91.7%**
- Simulated random-null coverage: **91.4% ± 0.3%**

The observed recovery rate was therefore consistent with what would be expected if labels were missing approximately at row level within clients.

### 3.5 Result

ClientId propagation recovered:

**16,159 of 17,631 missing policies**

or:

**91.65% of the originally missing population**

After this stage, only **1,472 policies** remained unresolved.

---

## 4. Why the ML Problem Had to Be Reframed

At first glance, the remaining missing labels suggested a standard multiclass classification problem.

However, policy-level modeling would have introduced a major weighting problem.

One client in the dataset contains more than **10,000 policy records**, representing roughly one fifth of all rows.

If every policy were treated as an independent training observation, that client could dominate the model and create associations such as:

```text
specific geography
+ specific coverage mix
+ premium patterns
≈ industry
```

when the model was actually learning the repeated footprint of one entity.

This client also explained why some policy-level geographic associations initially looked stronger than they really were.

For the primary ML experiments, I therefore changed the unit of analysis to:

```text
1 ClientId = 1 modeling observation
```

This made the validation question much closer to the real business problem:

> Can the industry of a previously unseen client be inferred from the available portfolio characteristics?

---

## 5. Client-Level Feature Engineering

The modeling table aggregated policy information to client level.

Features evaluated included:

- policy count;
- total premium;
- average premium;
- total sum insured;
- average sum insured;
- premium / sum-insured ratios;
- policy-duration statistics;
- portfolio span / tenure;
- dominant state;
- dominant municipality;
- number of distinct states;
- number of distinct municipalities;
- number of coverage types;
- coverage-mix shares.

The target remained the observed client industry.

The modeling design avoided using information that directly leaked the same client's label across train and validation observations.

---

## 6. Testing Whether Basic Portfolio Fields Predict Industry

Before relying on complex models, I tested whether obvious categorical combinations generalized to unseen clients.

Approximate out-of-sample accuracies included:

| Feature / combination | Accuracy |
|---|---:|
| Majority-client baseline | 14.94% |
| Year | 15.07% |
| Coverage | 14.94% |
| State | 14.08% |
| Municipality | 12.83% |
| Year + Coverage | 14.32% |
| Year + State | 13.21% |
| Coverage + State | 12.20% |
| Year + Municipality | 11.19% |
| Coverage + Municipality | 9.69% |

These results showed that apparent policy-level relationships did not generalize to new clients.

This was an important distinction:

> A variable can be associated with missingness or repeated-client structure without being useful for unseen-client industry prediction.

---

## 7. Multiclass Machine Learning Benchmark

The problem contains **15 industry classes**.

A balanced random benchmark is therefore approximately:

- balanced accuracy: **6.67%**;
- Top-2 accuracy: **13.33%**;
- Top-3 accuracy: **20.00%**.

### Cross-validated results

| Model | Accuracy | Balanced Accuracy | Macro F1 | Log Loss | Top-2 | Top-3 |
|---|---:|---:|---:|---:|---:|---:|
| LightGBM | 6.42% | 6.80% | 6.13% | 2.704 | 13.54% | 21.30% |
| XGBoost | 6.36% | 6.76% | 6.08% | 2.705 | 13.63% | 21.42% |
| CatBoost | 5.36% | 6.14% | 4.90% | 2.705 | 12.44% | 19.64% |

The strongest model was essentially at the balanced random baseline.

A simplified validation also produced:

- model accuracy: **14.82%**;
- majority-class dummy: **14.82%**;
- macro F1: ~**1.72%**.

A policy-level CatBoost experiment aggregated back to client level produced:

- client accuracy: **15.09%**;
- dummy accuracy: **14.82%**.

The gain was far too small to justify production use.

### Capacity versus generalization

CatBoost achieved substantially higher training performance than validation performance in one capacity check.

This showed that the algorithms were capable of fitting structure in the training sample but that the structure did not generalize reliably to unseen clients.

That is exactly the type of result where adding more model complexity would risk improving memorization rather than business value.

---

## 8. Alternative Signal Tests

I did not stop after one family of models.

Several independent tests were used to determine whether the failure was specific to a particular algorithm or reflected a deeper lack of predictive signal.

### 8.1 Client-name text modeling

Client names were normalized and modeled using word and character TF-IDF features with Logistic Regression.

Grouped validation was used so that name variants did not leak between train and validation.

Results:

- accuracy: **11.6%**;
- balanced accuracy: **6.4%**;
- majority baseline: **14.9%**.

Permutation-null testing also showed that the result was not meaningfully above chance expectations.

This was consistent with a broader data-quality observation: many company names look generic, repeated or anonymized and are not reliable semantic proxies for industry.

### 8.2 Clustering

K-Means was tested with several values of `k`.

Adjusted mutual information between clusters and industry remained approximately zero and below permutation-based expectations.

The feature space therefore did not naturally separate into industry-like groups.

### 8.3 One-vs-rest classification

Binary one-vs-rest classifiers were evaluated for individual industries.

AUC values remained around the no-skill region and did not provide robust evidence that any industry was consistently separable from the rest.

### 8.4 Final ML conclusion

The conclusion was consistent across:

- gradient-boosted multiclass models;
- simplified baselines;
- policy-level sensitivity tests;
- text classification;
- clustering;
- one-vs-rest classification;
- basic categorical combinations.

Therefore:

> **With the variables available in this portfolio, there is no evidence of sufficient out-of-sample predictive signal to reliably infer industry for previously unseen clients.**

ML predictions were **not** written into `industry_final`.

This was a deliberate quality decision, not an inability to produce a model.

---

## 9. Client Names and Entity Semantics

The raw client-name field also required careful interpretation.

The data contained many repeated or generic naming patterns, and exact company names could appear under several different `ClientId`s and industries.

Examples of common structures included terms such as:

- Distribuidora;
- Grupo;
- Corporativo;
- Comercializadora;
- Tecnologías;
- Transportes;
- Constructora;
- Servicios.

Because of this, a name such as “Transportes X” could not safely be assigned to Transportation purely from lexical meaning.

The workflow therefore followed this rule:

> First resolve identity; only then consider economic activity; never classify industry solely from how the name sounds.

This also explained why text-only models performed poorly.

---

## 10. External Entity Resolution

After deterministic recovery and ML feasibility testing, external enrichment was used for a small subset of unresolved clients.

The process separated:

1. entity identification;
2. principal economic activity;
3. mapping to the supplied industry taxonomy.

### External backtest

Before accepting the method broadly, I tested it on **45 clients with known source industries**.

Results:

- **41** abstentions;
- **4** candidate classifications;
- **0** candidate classifications matching the portfolio's known industry.

This result suggested that real-world company classification and the synthetic/anonymized portfolio labels were not reliably aligned.

For that reason, external enrichment was deliberately constrained and assigned lower confidence.

### Final external contribution

The accepted external layer contributed:

- **116 policies**;
- **52 clients**;
- **88** policies at `medium_low` confidence;
- **28** policies at `low` confidence.

External fills were never allowed to overwrite original or ClientId-derived industries.

---

## 11. Explicit Abstention

After all recovery stages, **1,356 policies** remained unresolved.

I chose not to:

- assign the majority industry;
- use weak model predictions;
- classify from name semantics;
- drop the rows.

Instead, the reporting layer exposes them as:

```text
Unresolved
```

This preserves portfolio completeness while making residual uncertainty visible.

That decision is especially important because a dashboard can otherwise appear more precise than the underlying data actually supports.

---

## 12. Client Name Normalization for Reporting

Industry recovery and client-name normalization were kept as separate problems.

`ClientId` remains the actual identity key.

For reporting, I created a conservative display-name process:

1. minimally clean whitespace and control characters;
2. create a normalized matching key for grouping formatting variants;
3. remove common legal suffix differences only from the matching key;
4. identify the dominant name family within each `ClientId`;
5. choose an **observed source variant** as the reporting name.

The selected display name prefers:

- more complete wording;
- more words;
- longer / more explicit formatting;
- mixed case over all-uppercase when available;
- higher exact frequency;
- earliest date only as a final tie-breaker.

No semantic business terms are invented.

---

## 13. Portfolio Concentration and Duplicate Checks

During dashboard validation, one client emerged as an extreme concentration case.

That client contains more than 10,000 policies and contributes a material share of portfolio premium.

Because such a client can distort:

- client rankings;
- geographic summaries;
- policy-level associations;
- aggregate growth interpretation,

I specifically tested whether the concentration was caused by accidental duplication.

Checks found:

- **0 duplicated `policy_id`s**;
- **0 fully duplicated rows**;
- no duplicate combination of premium, sum insured and coverage for that client;
- no evidence that its total premium was created by a join or repeated policy record.

The client was therefore retained.

The correct interpretation is **portfolio concentration**, not data duplication.

This also reinforced the decision to model industry at client level rather than policy level.

---

## 14. Reporting and Dashboard Design

The final reporting dataset preserves one row per policy and exposes:

```text
ClientId
policy_id
client_name
state
municipality
coverage_type
industry
premium
sum_insured
policy_start_date
policy_end_date
fill_method
confidence_level
```

Unresolved industries are represented as `Unresolved`.

The dashboard uses a dedicated Calendar table and DAX time-intelligence measures for:

- Total Premium;
- Previous Year Premium;
- Premium Growth (amount; currency assumed MXN);
- Premium Growth %;
- Total Clients;
- Total Policies.

Field parameters allow a single visual to dynamically switch among:

- Industry;
- State;
- Municipality;
- Coverage Type;
- Client.

A second parameter allows users to switch between Premium and Premium Growth.

This keeps the dashboard compact while preserving analytical flexibility.

---

## 15. Key Choices

### Deterministic evidence before predictive complexity

A validated same-client label is more defensible than a complex model operating at baseline performance.

### Client-level validation

The prediction target is a client, not a policy row. Client-level validation prevents repeated entities from dominating the experiment.

### Reject ML when it does not generalize

The goal was not to force a machine-learning component into production.

The correct production decision can be **not to use the model**.

### Separate confidence tiers

Original, ClientId-derived, external and unresolved records are distinguishable in the final output.

### Keep uncertainty visible

`Unresolved` is preferable to an unsupported industry label.

### Keep concentrated but valid business

A large client should not be removed only because it makes a chart difficult to scale.

---

## 16. What I Would Do Differently With More Time or Better Data

The main limitation is not model capacity. It is the lack of stronger explanatory attributes for previously unseen clients.

### 16.1 Add stronger business attributes

The highest-value additions would be:

- SCIAN / NAICS codes;
- tax or commercial registry identifiers;
- verified legal entity names;
- an internal governed company master;
- richer broker and account variables;
- underwriting descriptors;
- product information tied directly to the insured operation.

These features are much closer to the actual concept being predicted than geography or premium.

### 16.2 Build a human-review process

I would create a controlled review queue for ambiguous external matches containing:

- matched entity;
- proposed industry;
- evidence;
- confidence;
- alternative candidates.

This would allow the remaining `Unresolved` population to be reduced safely.

### 16.3 Productionize data-quality controls

I would add automated monitoring for:

- duplicate policy IDs;
- new client-industry conflicts;
- unresolved-rate changes;
- fill-method distribution;
- industry-mix drift;
- refresh failures;
- changes in external reference mappings.

### 16.4 Revisit ML only with better signal

I would not spend more time tuning the same feature set.

Once richer client attributes were available, I would rerun the same leakage-safe client-level benchmark and require clear improvement over naive baselines before deployment.

### 16.5 Extend portfolio analytics

Additional dashboard work could include:

- contribution-to-growth analysis;
- concentration ratios;
- top positive and negative movers;
- client drill-through;
- sensitivity views comparing total portfolio performance with performance excluding dominant accounts.

---

## 17. Conclusion

The main analytical result is not a specific algorithm.

It is the decision framework used to determine when a classification is defensible.

The workflow:

- uses direct internal evidence first;
- validates deterministic rules empirically;
- tests predictive approaches rather than assuming they are useful;
- rejects ML when it fails to generalize;
- treats external information as lower-confidence evidence;
- keeps unresolved cases visible;
- preserves concentrated but valid business records.

The result is a reporting dataset that is substantially more complete without sacrificing auditability or creating unsupported precision.

> **The goal was not to fill every missing value; it was to maximize usable coverage while keeping every classification defensible.**
