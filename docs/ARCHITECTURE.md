# Architecture

## Runtime

```text
licensed workbooks
       │
       ▼
etl/build_feature_tables.py ──► artifacts/etl (generated, ignored)
       │
       ▼
pipeline/modeling.py ─────────► artifacts/selected_model (generated, ignored)
       │
       ▼
prototype/service.py
   ├── prototype/api.py ──────► frontend/src/components/scenario-app.tsx
   └── prototype/app.py       (Streamlit client)
```

The final pipeline fits one pooled Poisson XGBoost estimator. The shared service
combines that model with the transparent scenario chain. Streamlit calls the
service functions directly; Next.js calls the same service through FastAPI.

## Main boundaries

| Location | Responsibility |
| --- | --- |
| `etl/` | Normalize grains, preserve missingness, and build auditable features. |
| `pipeline/` | Own the frozen B0 feature schema and selected estimator. |
| `prototype/scenario_engine.py` | Convert editable aviation assumptions into arrival changes. |
| `prototype/service.py` | Canonical scenario contract and shared calculations. |
| `prototype/api.py` | Typed HTTP boundary for the custom dashboard. |
| `prototype/app.py` | Streamlit dashboard. |
| `frontend/` | Next.js dashboard with control parity. |
| `tests/` | Model, reconciliation, API, and control-contract checks. |

## Training and evaluation

`prototype/train_models.py` rebuilds ETL data when necessary, holds out
2024-08-01–2025-02-28, evaluates the fixed pooled Poisson definition, then
refits through 2025-07-31 for official-test scenario use. Fitted files and
row-level predictions are written below `artifacts/` and are not committed.

Model/feature selection happened before the final holdout comparison, using two
rolling chronological validation folds. Frozen source and aggregated evidence
are in `archive/experiments/`.

## Scenario contract

`prototype.service.SCENARIO_CONTROL_KEYS` is canonical. Any change to inputs,
units, defaults, ranges, or interpretation must update both dashboards, the API,
tests, and `UI_SCENARIO_PARITY.md` in one task.

The scenario engine distinguishes:

1. scheduled seats;
2. passengers after load factor;
3. destination passengers after transfer/transit removal;
4. visitors and hotel arrivals after explicit conversion assumptions;
5. pooled-model hotel-demand output.

These are planning responses, not causal estimates.
