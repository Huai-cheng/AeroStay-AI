# Selected forecasting pipeline

This folder contains the only serving model: the 14-feature **B0 pooled Poisson
XGBoost**. `modeling.py` owns loading, feature construction, preprocessing,
training, serialization, and prediction. `prototype/train_models.py` performs
the chronological back-test and refits this pipeline for the dashboard.

Historical models and feature/loss searches are intentionally separated under
`archive/experiments/`; they are evidence, not production alternatives.
