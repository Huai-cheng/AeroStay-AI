# Offline modelling pipelines

These pipelines were created independently from the existing solution. They share one
leakage-safe benchmark runner so every approach uses the same dates, feature definitions,
and metrics.

Run:

```powershell
.\.venv\Scripts\python.exe pipelines\common\run_offline_benchmark.py
```

The locked offline test period is 2024-08-01 through 2025-02-28 (212 days).
The official 2025-08-01 through 2026-02-28 target-free files are not used for scoring.

## Registered approaches

- `seasonal_naive`: same calendar date one year earlier.
- `regularized_linear`: ridge regression with calendar, demand, and aviation features.
- `demand_xgboost`: XGBoost using demand/history features.
- `aviation_xgboost`: XGBoost using aviation/history features without supplied arrivals.
- `hybrid_residual_xgboost`: XGBoost correction over the prior-year prediction.
- `pooled_catboost`: residual CatBoost with native market categories.
- `lightgbm_residual`: LightGBM correction over the prior-year prediction.
- `interpretable_gam`: additive spline and categorical ridge model.
- `hierarchical_rate_model`: partially pooled market-month arrival conversion rates.
- `ensemble_blend`: fixed blend of residual XGBoost and CatBoost.

Detailed predictions and metric tables are written under `artifacts/offline_metrics/`.

