# Build architecture and interfaces

This describes the implemented prototype. Local terminal, API, and web checks passed. Container execution has not yet been verified on this host.

## Repository layout

```text
config/project.yaml            Versioned paths, split dates, model and service settings
data/                          Supplied competition files (current location)
artifacts/processed/           Rebuilt monthly tables and data-quality reports
src/dtc/data.py                Ingest, clean, aggregate, validate, and map markets
src/dtc/model.py               Baselines, training, evaluation, serving bundles
src/dtc/scenario.py            Transparent chain, uncertainty, sensitivity
src/dtc/api.py                 FastAPI prediction and scenario endpoints
src/dtc/web.py                 Streamlit planner interface
artifacts/runs/<run_id>/       Models, metrics, predictions, manifests, reports
tests/                         Model and scenario invariants
journal/YYYY-MM-DD.md           Decisions and measured results by workday
Dockerfile                     Reproducible Python runtime
compose.yaml                   API and web services; optional training job
```

The ETL reads the supplied files without modifying them and writes derived tables under `artifacts/processed/`. Generated files and private competition data should be excluded from a public repository unless sharing is allowed.

## YAML configuration

[`config/project.yaml`](config/project.yaml) controls paths, split dates, model choice, random seed, assumptions, and service ports. The loader validates required sections and parameter bounds. The prototype's visitor share and origin-to-nationality allocation are explicit, unobserved assumptions; overrides appear in each response.

Each training run copies the resolved configuration into its output folder and records input-file hashes, source-code hash, and library versions.

## Separate pipeline stages

Each stage is a callable function and terminal subcommand. A stage reads its declared inputs and writes its own outputs, so failures can be found without rerunning everything.

| Stage | Main work | Output |
| --- | --- | --- |
| `audit` | Read source files; check dates, missing values, and count identities against the dictionary. | Data-quality report. |
| `prepare` | Normalize dates and country labels; aggregate flight counts and hotel records to their correct monthly grains. | Origin-month and nationality-month tables. |
| `map-markets` | Build an explicit assumed origin-to-nationality allocation; preserve unknown share. | Allocation table with shares summing to one. |
| `features` | Build training features from information available at forecast time. | Model-ready monthly table and schema. |
| `split` | Create time-ordered train and holdout partitions. | Split manifest. |
| `train` | Compare seasonal, seat-adjusted, regression, and XGBoost models on 2024 data; fit the selected model. | Model files, selection metrics, and manifest. |
| `evaluate` | Predict held-out periods end to end and compare with known hotel results. | Predictions, WMAPE, MAE, bias, market/month breakdowns. |
| `package` | Mark an evaluated run as the selected serving bundle. | `artifacts/selected.json`. |

The app and API only **load** a packaged model. They do not retrain when a user moves a slider.

## Model inputs and targets

The scenario engine starts with departure origin, month, change in flights per week, seats per flight, and planned load factor. A negative frequency change represents a reduction. Transfer/transit share, nonresident visitor share, hotel conversion, and length of stay are estimated parameters or visible user overrides. The origin-to-nationality mapping is a separate, versioned assumption.

The monthly training table has one row per `month × hotel nationality`. Model inputs are month, nationality, allocated scheduled seats, citywide scheduled seats, and last year's hotel arrivals. The selected seat-adjusted seasonal model uses last year's arrivals multiplied by a capped year-over-year allocated-seat ratio raised to elasticity 0.75. The primary observed target is monthly hotel check-ins, calculated from daily `New Arrivals`. A secondary observed target is the sum of daily `Guests`, called **guest-days** until its relation to overnight guest nights is verified. Future realised passenger counts and hotel arrivals are not used in the holdout forecast.

The supplied train period is January 2022–July 2025. Model choice uses 2024, then January–July 2025 is held out for reported accuracy. The serving baseline is refitted through July 2025 after evaluation. The official August 2025–February 2026 test files lack `Guests` labels, so they cannot yield offline WMAPE for that target without released answers.

## Terminal commands

```powershell
python -m dtc.cli audit --config config/project.yaml
python -m dtc.cli prepare --config config/project.yaml
python -m dtc.cli map-markets --config config/project.yaml
python -m dtc.cli features --config config/project.yaml
python -m dtc.cli split --config config/project.yaml
python -m dtc.cli train --config config/project.yaml
python -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
python -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
python -m dtc.cli predict --config config/project.yaml --month 2025-12
python -m dtc.cli predict-official --config config/project.yaml
python -m dtc.cli serve --config config/project.yaml
```

`train` invokes the preparation stages and prints the run ID and artifact path. `evaluate` prints metrics and saves per-market predictions. Nonzero exit codes indicate invalid configuration, missing data, or a failed stage.

Container equivalents are defined for hosts with a running Docker daemon:

```powershell
docker compose run --rm api python -m dtc.cli train --config config/project.yaml
docker compose run --rm api python -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
docker compose run --rm api python -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
docker compose up api web
```

`compose.yaml` mounts competition data read-only and persists processed data and run artifacts in local folders. The API and web services load the same selected model bundle.

## API contract

- `GET /health`: service and selected-model status.
- `GET /v1/model`: model version, training period, target definitions, and validation metrics.
- `POST /v1/predict`: baseline monthly hotel check-ins and estimated guest nights by nationality.
- `POST /v1/scenarios/simulate`: baseline and modified flight plan; return the conversion chain, market/month outputs, uncertainty range, sensitivity, and warnings.

Example terminal call after the API is running:

```powershell
$scenario = Get-Content -LiteralPath 'examples/delhi_december_2025.json' -Raw
Invoke-RestMethod -Uri 'http://localhost:8000/v1/scenarios/simulate' -Method Post -ContentType 'application/json' -Body $scenario
```

The response must identify units and distinguish departure country from guest nationality. Invalid dates or rates return a clear 4xx error. Save or export a scenario with its input JSON, resolved assumptions, model/run IDs, and resulting figures.

## Run artifact layout

```text
artifacts/runs/<run_id>/
  config.resolved.yaml
  manifest.json               Input hashes, code version, time, model type
  model/                      Fitted estimators or selected parametric settings
  metrics/summary.json
  metrics/by_month.csv
  metrics/by_market.csv
  predictions/holdout.csv
  predictions/official_monthly.csv  Created by predict-official
  reports/data_quality.json
  reports/split_manifest.json
  reports/market_allocation_assumption.csv
```

Each training run has a unique ID. `artifacts/selected.json` points the API to the chosen evaluated run.

## Verification gates

1. Data totals and `P2P = PAX − transfer − transit` reconcile, subject to documented exceptions.
2. Every feature in validation is available at the simulated forecast date.
3. The same scenario produces equivalent results through Python, the API, and the web app.
4. Added seats with fixed conversion assumptions cannot decrease the transparent-chain estimate.
5. The API rejects invalid shares and returns model/data provenance.
6. Fresh Docker build plus terminal train and API call succeed from documented commands.
