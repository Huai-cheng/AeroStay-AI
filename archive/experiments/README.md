# Experiment catalog

These challengers are retained for auditability and are not imported by the
application.

| Family | Question tested |
| --- | --- |
| Seasonal naive | Does last year's seasonal value remain a competitive floor? |
| Regularized linear | Is a simple additive relationship sufficient? |
| Demand XGBoost | Can nonlinear demand/history interactions improve accuracy? |
| Aviation XGBoost | Can flight-side variables predict without supplied arrivals? |
| Hybrid residual XGBoost | Can boosting correct a prior-year baseline? |
| Pooled CatBoost | Do native categorical splits improve market handling? |
| LightGBM residual | Does a second tree implementation improve residual learning? |
| Interpretable additive model | Can splines retain accuracy with clearer effects? |
| Hierarchical rate model | Do partially pooled arrival-conversion rates help sparse markets? |
| Ensemble blend | Do complementary model errors improve the aggregate? |
| XGBoost loss search | Compare squared error, log-target, Poisson, pseudo-Huber, and constraints. |
| Feature-group search | Test historical, capacity/network, passenger, and origin-market additions. |
| Pooled Poisson feature search | Rolling ablations and final B0 selection. |

`results/pooled_poisson_feature_search/model_benchmarks.csv` is the compact
model comparison used in the main README. The larger tables contain rolling
folds, market/month breakdowns, feature coverage, and correlation evidence.
Row-level predictions are deliberately not committed.
