# Data ETL and feature contracts

This directory owns the transformation from the licensed raw workbooks in
`data/` to model-ready, time-safe feature tables.  The raw workbooks are never
modified.

## Canonical grains

The ETL deliberately keeps more than one grain.  Converting everything to a
single monthly table would destroy the daily hotel signal, while pretending
that the 2022 monthly flight observations are daily would create false rows.

| Table | Grain | Purpose |
| --- | --- | --- |
| `hotel_daily.csv` | date, segment, hotel nationality market | Daily demand models |
| `flight_origin_monthly.csv` | month, departure country | Common-grain aviation history |
| `flight_global_monthly.csv` | month | Global capacity and passenger context |
| `route_monthly.csv` | month, route | Route openings, closures and frequency |

Counts and flows are summed. Ratios and shares are always recalculated from
aggregated numerators and denominators; they are never averaged. The sum of
daily `Guests` is labelled guest-days, not unique monthly guests.

## Run

```powershell
.\.venv\Scripts\python.exe etl\build_feature_tables.py
```

Generated files are written under `artifacts/etl/`, which is excluded from
version control because it is derived from competition-licensed data.

## Feature governance

`feature_registry.csv` is the source of truth for feature decisions. Any new
feature must be added to the registry with:

- source and grain;
- whether it is known at forecast time;
- missing-value policy;
- model/scenario role;
- keep, test, assumption, or drop decision;
- a short reason.

Availability in ETL does not imply automatic model inclusion. New model
features must beat the existing feature set in chronological validation or
materially improve scenario validity without introducing leakage.

## Missing values and sparse feature families

Do not zero-pad a missing value unless zero genuinely means none. XGBoost can
learn a default direction for `NaN`; systematic missingness may also receive a
separate indicator.

Do not fit the full-history model, wait for a batch containing a sparse feature,
and then continue training only on that batch. Later boosting rounds would see
a different data distribution and optimize residuals only for that subset.
This is not analogous to transformer padding.

For a partially covered feature:

1. retain all rows and represent unavailable values as `NaN`;
2. add a coverage indicator when missingness is meaningful;
3. tune on rolling, chronological folds;
4. compare on a common-coverage validation window;
5. keep the feature only if performance and stability improve.

Cabin-class features are excluded from the selected set for now because they
are incomplete early in the history, highly correlated with total seats and
passenger totals, and add complexity without a demonstrated planning benefit.

## Tested aviation additions

The ETL builds the obtainable additions below for scenario calculations,
reporting, and reproducible experiments. Chronological ablation testing did not
show a stable pooled-forecast improvement, so they are not inputs to the final
B0 model.

- Previous-year same-day guests.
- Total scheduled seats by month.
- Average weekly flight frequency, first averaged within route-month.
- Active route count.
- New-route count and discontinued-route count.
- Point-to-point, transfer and transit passenger shares.
- Reconstructed passenger load factor.
- Departure-country seat and passenger shares.
- Origin-market seat concentration.
- Year-over-year seat and frequency changes.

Potential future extensions—event indicators, source-market holidays,
Ramadan/Eid effects, and a confidence-scored origin-to-nationality mapping—need
authoritative sources before testing. They are not silently synthesized.
