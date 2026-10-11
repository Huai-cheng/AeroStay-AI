# Feature-group XGBoost experiments

This pipeline compares four target/loss treatments across controlled feature
groups using chronological tuning, validation and offline-test periods.

```powershell
.\.venv\Scripts\python.exe pipelines\feature_group_xgboost\run_experiments.py
```

Outputs are written to `artifacts/feature_group_xgboost/`. Cross entropy is a
diagnostic binned-classification formulation because the supplied target is a
count rather than a class label.

