# Reporting Data Dictionary

One row represents one policy. The CSV is UTF-8, comma-delimited, with a header.
Import quoted text using a CSV parser; do not split strings manually. Preserve
column names and accents to avoid breaking the downstream model.

| Field | Suggested type | Meaning / rule |
| --- | --- | --- |
| `ClientId` | Text | Client identity key; preserve exact text |
| `policy_id` | Text | Unique policy key |
| `client_name` | Text | Normalized display name; not a unique identity key |
| `state` | Text | Client state; 22 observed values |
| `municipality` | Text | Municipality; 109 observed values; qualify by state for geographic grouping |
| `coverage_type` | Text | Coverage label; seven observed values |
| `industry` | Text | 15 known industry labels plus `Unresolved` |
| `premium` | Decimal / fixed decimal | Source premium amount; currency unspecified, MXN assumed |
| `sum_insured` | Decimal / fixed decimal | Source sum insured; same currency assumption |
| `policy_start_date` | Date | ISO `YYYY-MM-DD`; proposed premium-period date |
| `policy_end_date` | Date | ISO `YYYY-MM-DD`; must not precede start date |
| `fill_method` | Text | `original`, `client_id`, `llm_external`, `unresolved` |
| `confidence_level` | Text | Qualitative tier: `high`, `medium_low`, `low`, `unresolved` |

Original and same-client methods use `high`; external candidates use `medium_low`
or `low`; unresolved uses `unresolved`. A confidence tier is not a calibrated
probability. Empty strings and `Unresolved` are not interchangeable.

Source numbers use a decimal point without thousands separators. Dates should be
parsed explicitly; identifiers remain text. There is no currency code or exchange
rate in this file, and renaming a measure to USD would not convert the amounts.

For Power BI, use fixed decimal amounts where appropriate and a date relationship
based on the agreed period definition. A client dimension must have one row per
`ClientId`, and location should use state plus municipality where names collide.

The reporting CSV does not contain original industry values, external source URLs,
model predictions, match explanations or pipeline versions. It is a reporting
snapshot, not a complete audit or lineage dataset.
