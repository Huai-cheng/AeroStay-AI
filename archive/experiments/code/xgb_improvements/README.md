# XGBoost improvement experiments

Focused international-model experiments using a pre-holdout validation period for
early stopping and a locked 212-day offline test for final scoring.

Implemented variants:

- `xgb_clean_earlystop`
- `xgb_tuned_square`
- `xgb_log1p`
- `xgb_poisson`
- `xgb_pseudohuber`
- `xgb_prior_year_residual`
- `xgb_native_categorical`
- `xgb_monotonic_arrivals`

Run all experiments with:

```powershell
.\.venv\Scripts\python.exe pipelines\xgb_improvements\run_experiments.py
```

Results are written to `artifacts/xgb_improvements/`.

