# Pooled Poisson feature-combination results

Feature selection used two rolling chronological validation windows. The final test period (2024-08-01 to 2025-02-28) was opened only for predeclared anchors and validation-selected finalists.

## Main result

- Best rolling-validation experiment: **Z3_frequency_plus_concentration** at **11.70%** WMAPE.
- Best schedule-safe experiment: **Z3_frequency_plus_concentration** at **11.70%** WMAPE.
- Finalists evaluated once on test: B0_current_baseline, L0_lean_core, S4_compact_scheduled, Z3_frequency_plus_concentration, R1_baseline_plus_scheduled_passenger_proxy.
- **Final Poisson recommendation: keep `B0_current_baseline`.** The validation winner did not reproduce its gain on the untouched test period.
- Challenger minus baseline: +0.11% WMAPE; paired month-cluster bootstrap 95% interval +0.02% to +0.22%.

## Rolling-validation leaderboard

| Rank | Experiment | Features | WMAPE | vs current | Domestic | International | Bias | Fold SD |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Z3_frequency_plus_concentration | 16 | 11.70% | -0.16% | 6.17% | 16.46% | 0.25% | 0.10% |
| 2 | Z8_frequency_plus_total_seats | 16 | 11.75% | -0.12% | 6.22% | 16.50% | 0.50% | 0.02% |
| 3 | A5_baseline_plus_weekly_frequency | 15 | 11.77% | -0.09% | 6.17% | 16.59% | 0.46% | 0.12% |
| 4 | Z6_frequency_prior_same_day_breadth_mix | 18 | 11.79% | -0.08% | 6.18% | 16.61% | 0.83% | 0.02% |
| 5 | A7_baseline_plus_breadth_mix | 16 | 11.82% | -0.05% | 6.03% | 16.79% | 0.49% | 0.02% |
| 6 | Z2_frequency_plus_active_routes | 16 | 11.82% | -0.05% | 6.24% | 16.62% | 0.28% | 0.05% |
| 7 | Z7_frequency_level_and_growth | 16 | 11.82% | -0.04% | 6.30% | 16.57% | 0.28% | 0.17% |
| 8 | R1_baseline_plus_scheduled_passenger_proxy | 15 | 11.83% | -0.04% | 6.28% | 16.61% | 0.75% | 0.15% |
| 9 | A5_baseline_plus_yoy_frequency | 15 | 11.84% | -0.03% | 6.22% | 16.68% | 0.47% | 0.07% |
| 10 | A5_baseline_plus_active_routes | 15 | 11.85% | -0.02% | 6.20% | 16.71% | 0.57% | 0.02% |
| 11 | A5_baseline_plus_seat_concentration | 15 | 11.85% | -0.01% | 6.14% | 16.76% | 0.45% | 0.15% |
| 12 | A4_baseline_plus_prior_same_day | 15 | 11.86% | -0.01% | 6.27% | 16.67% | 0.62% | 0.00% |
| 13 | B0_current_baseline | 14 | 11.87% | +0.00% | 6.21% | 16.73% | 0.47% | 0.18% |
| 14 | A5_baseline_plus_total_seats | 15 | 11.87% | +0.01% | 6.24% | 16.71% | 0.55% | 0.09% |
| 15 | A5_baseline_plus_departure_countries | 15 | 11.88% | +0.01% | 6.27% | 16.70% | 0.65% | 0.18% |

## Held-out test results

| Model | WMAPE | Domestic | International | Bias | MAE | RMSE | Macro-market WMAPE | P90-market WMAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B0_current_baseline | 12.99% | 7.64% | 16.24% | 2.73% | 117.45 | 300.45 | 19.99% | 28.38% |
| Z3_frequency_plus_concentration | 13.10% | 7.88% | 16.27% | 2.79% | 118.49 | 306.04 | 19.72% | 27.85% |
| L0_lean_core | 13.22% | 6.45% | 17.34% | 1.58% | 119.59 | 287.49 | 21.38% | 31.08% |
| R1_baseline_plus_scheduled_passenger_proxy | 13.31% | 8.55% | 16.20% | 3.40% | 120.36 | 315.03 | 19.83% | 28.37% |
| S4_compact_scheduled | 13.53% | 7.11% | 17.44% | 1.95% | 122.40 | 297.57 | 21.14% | 29.83% |

## Required model comparisons on the selected feature definition

| Model | Features | WMAPE | Domestic | International | Bias | MAE | RMSE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pooled XGBoost Poisson | B0_current_baseline | 12.99% | 7.64% | 16.24% | 2.73% | 117.45 | 300.45 |
| Pooled XGBoost log-target | B0_current_baseline | 13.00% | 8.48% | 15.75% | 1.19% | 117.60 | 320.88 |
| Lean pooled XGBoost Poisson | L0_lean_core | 13.22% | 6.45% | 17.34% | 1.58% | 119.59 | 287.49 |
| Pooled XGBoost squared-error | B0_current_baseline | 13.50% | 7.68% | 17.03% | 3.01% | 122.05 | 313.10 |
| Linear regression (Ridge) | B0_current_baseline | 21.84% | 8.82% | 29.75% | 1.22% | 197.51 | 403.35 |

## Feature definitions

- **Final pooled Poisson baseline:** linear time trend; annual sine and cosine; weekend; new arrivals; same-day guests plus missing indicator; previous-year total guests; previous-year new arrivals; year-over-year arrival ratio; market; month; day of week; domestic/international segment.
- **Validation challenger:** the complete baseline plus average weekly flight frequency and global departure-country seat concentration.
- **Lean comparison:** trend; new arrivals; same-day guests plus missing indicator; previous-year total guests; market; segment; month; day of week.
- **Compact scheduled comparison:** lean/historical core plus total seats, year-over-year seat change, active-route count and seat concentration.

## Data verification findings

- 8 candidate features have less than 75% overall non-null coverage; see `feature_coverage.csv`.
- Global aviation values exist at monthly grain and are repeated over daily hotel rows. Rolling time validation, not random row splitting, is therefore mandatory.
- Passenger load factor and passenger shares are realized historical values. They are conditional model inputs unless a planned/forecast value is provided at scenario time.
- Departure-origin features were excluded from this pooled search because departure country is not the same entity as hotel guest nationality.
- Highly related pairs are documented in `feature_correlations.csv`; correlation is measured over unique months rather than repeated daily rows.

## Interpretation rule

The production recommendation prioritizes rolling validation, forecast-time availability, domestic/international stability, and scenario meaning. The held-out test is evidence, not a new feature-selection loop.
