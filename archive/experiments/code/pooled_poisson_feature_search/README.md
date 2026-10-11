# Pooled Poisson feature search

This pipeline selects features for one pooled domestic/international Poisson
XGBoost model. Feature combinations are selected with rolling chronological
validation. The final August 2024 through February 2025 period is used only for
the prespecified baselines and validation-selected finalists.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe pipelines\pooled_poisson_feature_search\run_search.py
```

Outputs are written to `artifacts/pooled_poisson_feature_search/`.
