# AeroStay Intelligence

An explainable aviation-to-hotel demand simulator for the DCT Abu Dhabi
challenge. The product combines one pooled Poisson XGBoost forecast with a
transparent scenario chain so planners can change flight capacity and
conversion assumptions, then inspect the resulting hotel-demand estimate.

## Selected model

The serving model is **one pooled XGBoost regressor with a Poisson count
objective**. Domestic and international rows are learned together; segment is
retained as a categorical feature. The frozen `B0` feature definition contains
14 inputs before one-hot encoding:

- time trend, cyclic annual seasonality, weekend, month, and weekday;
- domestic/international segment and hotel nationality market;
- current new arrivals and same-day guests, including a missingness flag;
- previous-year guests and arrivals, plus year-over-year arrival ratio.

Model selection used two chronological rolling validation folds. The final
comparison period was held out from feature and loss selection.

| Model | Combined WMAPE | Domestic WMAPE | International WMAPE |
| --- | ---: | ---: | ---: |
| **Pooled XGBoost Poisson (selected)** | **12.99%** | 7.64% | 16.24% |
| Pooled XGBoost log-target | 13.00% | 8.48% | **15.75%** |
| Lean pooled XGBoost Poisson | 13.22% | **6.45%** | 17.34% |
| Pooled XGBoost squared-error | 13.50% | 7.68% | 17.03% |
| Ridge linear regression | 21.84% | 8.82% | 29.75% |

Lower WMAPE is better. These are results on the internal chronological
2024-08-01–2025-02-28 comparison period, **not a score on the unlabeled official
test files**. Full aggregated evidence is in
[`archive/experiments/results/pooled_poisson_feature_search`](archive/experiments/results/pooled_poisson_feature_search/RESULTS.md).

## Repository map

```text
pipeline/       selected B0 pooled Poisson model only
etl/            data normalization and feature-table construction
prototype/      shared FastAPI service and Streamlit dashboard
frontend/       matching Next.js scenario dashboard
tests/          API, model, and scenario invariants
docs/           requirements, architecture, data audit, and model specification
archive/        frozen challengers, experiment code/results, and internal notes
```

`prototype/app.py` and `frontend/src/components/scenario-app.tsx` are two
clients of the same scenario product. Their controls must remain synchronized;
see [`UI_SCENARIO_PARITY.md`](UI_SCENARIO_PARITY.md).

## Run locally

Prerequisites:

- Python 3.11 or newer (Python 3.12 was used for verification);
- `pip` with network access for the first dependency installation;
- the five licensed workbooks described in [`data/README.md`](data/README.md);
- Node.js 20.9 or newer and npm only if running the Next.js dashboard;
- free local ports 8000 (API), 8501 (Streamlit), and 3000 (Next.js).

Install the locked Python dependencies and train the model:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m prototype.train_models
```

Training must complete before the API or either dashboard is started. It builds
the ETL outputs automatically when they are absent and writes the selected model
under `artifacts/selected_model/`.

Start the shared API, Streamlit client, and optional Next.js client in separate
terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn prototype.api:app --port 8000
.\.venv\Scripts\python.exe -m streamlit run prototype\app.py
Set-Location frontend; npm ci; npm run dev
```

The Next.js client requires the API on port 8000. Streamlit executes the same
service functions locally but still requires the trained artifact. If only the
model and offline metrics are needed, stop after the training command; Node.js
and both dashboards are optional.

- Streamlit: <http://localhost:8501>
- Next.js: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest
Set-Location frontend
npm run lint
npm run build
```

## What is intentionally not committed

The supplied competition workbooks, derived row-level datasets, trained model
binaries, raw predictions, local environments, build output, caches, and logs
are excluded. They are either licensed, reproducible, machine-specific, or
unnecessarily expose row-level challenge data. We do commit source code,
configuration, tests, methodology, feature decisions, and aggregated experiment
metrics so judges can audit how the selected model was chosen.

See [`docs/JUDGE_REPOSITORY_GUIDE.md`](docs/JUDGE_REPOSITORY_GUIDE.md) for the
commit policy and claim boundaries.
