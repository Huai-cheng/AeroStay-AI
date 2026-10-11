# Data and selected-model specification

## Data roles

The hotel training files contain daily `Guests`, `New Arrivals`, and partially
observed `Same-Day Guests`; international rows also contain nationality. The
official August 2025–February 2026 files omit `Guests`, so they support forecast
generation but not an offline accuracy claim. Flight data supplies schedules,
capacity, passenger movements, transfer/transit counts, and origin information
at mixed historical grains.

Raw competition files stay under ignored `data/`. ETL-derived row-level tables
and predictions stay under ignored `artifacts/`.

## Target

The model predicts supplied daily `Guests`. The product reports an estimated
overnight-oriented value as:

```text
predicted guest nights = max(predicted Guests - Same-Day Guests, 0)
```

This is an operational derivation from the available fields, not a replacement
for an authoritative observed guest-night field.

## Final feature definition

The B0 pooled model has 14 pre-encoding inputs.

| Group | Inputs |
| --- | --- |
| Calendar/trend | Linear trend, annual sine, annual cosine, weekend, month category, weekday category |
| Market identity | Hotel nationality market, domestic/international segment |
| Current demand | New arrivals, same-day guests, same-day missing indicator |
| Historical demand | Previous-year guests, previous-year arrivals, year-over-year arrival ratio |

Numeric missing values are median-imputed with indicators. Categories are
most-frequent imputed and one-hot encoded with unknown values ignored.

## Estimator

The selected estimator is XGBoost with `count:poisson`, 1,080 trees, learning
rate 0.03, maximum depth 5, minimum child weight 15, row/column subsampling
0.85, L2 regularization 10, and L1 regularization 0.1. Random seed is 20261010.

One estimator learns domestic and international observations together. Segment
is a feature rather than a routing rule.

## Evaluation discipline

- Selection: two rolling, forward-only validation folds.
- Final comparison: 2024-08-01–2025-02-28, not used to pick feature additions.
- Primary metric: WMAPE; lower is better.
- Supporting metrics: bias, MAE, RMSE, R-squared, macro-market WMAPE, and
  90th-percentile market WMAPE.
- Report domestic and international slices even though the serving estimator is
  pooled.

The selected model reached 12.99% combined WMAPE on the internal comparison
period. This must not be described as an official test or leaderboard score.

## Scenario-only factors

Weekly flights, seats per flight, load factor, transfer share, transit share,
visitor share, hotel-capture rate, and origin-to-nationality allocation are
editable scenario levers. Additional flight/network features were tested as
direct predictors but did not provide a stable improvement over B0. Keeping
them in the transparent scenario layer avoids presenting conditional or noisy
historical values as reliable future model inputs.

## Limitations

- Departure origin and hotel nationality are different concepts.
- Same-day coverage is sparse internationally and explicitly modeled as missing.
- Visitor share, capture rate, and nationality allocation are assumptions where
  authoritative observations are absent.
- Events, holidays, hotel prices, room supply, observed average length of stay,
  and aircraft class were not consistently available.
- Scenario responses are conditional forecasts, not causal effects.
