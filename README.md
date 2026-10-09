# Abu Dhabi air-to-hotel demand simulator

This repository contains a working DCT Abu Dhabi challenge prototype: a monthly international hotel-demand forecast and a flight-change simulator with a terminal interface, HTTP API, and planner web app.

The model should make this chain visible:

`scheduled seats → arriving passengers → inbound visitors → hotel guests → hotel guest nights`

The key data problem is that an aviation **origin country** is the country from which a flight departed, while a hotel **source market** is a guest's nationality. They cannot be joined as though they were the same field.

## Project documents

| File | Purpose |
| --- | --- |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Challenge requirements, success criteria, scenario controls, outputs, and judging priorities. |
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | Planner workflow, app screens, model contract, and prototype acceptance checks. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Container, YAML, pipeline, terminal, API, and artifact contracts. |
| [DATA_AND_MODEL.md](DATA_AND_MODEL.md) | Data inventory, country reconciliation, modelling approach, assumptions, and validation rules. |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Build sequence, decisions to resolve, and a testable definition of done. |
| [SUBMISSION.md](SUBMISSION.md) | Ten-page PDF and 1–2 minute video content plan and submission checklist. |
| [journal/2026-10-09.md](journal/2026-10-09.md) | Today's decisions, next work, and later results summary. |

[`config/project.yaml`](config/project.yaml) controls paths, split dates, model candidates, assumptions, and ports. [ARCHITECTURE.md](ARCHITECTURE.md) describes pipeline outputs and the API contract.

## Run locally (PowerShell)

```powershell
python -m venv .venv
& .venv\Scripts\python.exe -m pip install -e '.[test]'
& .venv\Scripts\python.exe -m dtc.cli train --config config/project.yaml
& .venv\Scripts\python.exe -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
& .venv\Scripts\python.exe -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
& .venv\Scripts\python.exe -m dtc.cli predict-official --config config/project.yaml
& .venv\Scripts\python.exe -m dtc.cli serve --config config/project.yaml
```

Use the run ID printed by `train`. In another terminal, start the web app:

```powershell
& .venv\Scripts\python.exe -m streamlit run src/dtc/web.py
```

The API is at `http://localhost:8000` and the web app at `http://localhost:8501`. Call the prediction and scenario endpoints from a terminal:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/v1/predict' -Method Post -ContentType 'application/json' -Body '{"month":"2025-12"}'
$scenario = Get-Content -LiteralPath 'examples/delhi_december_2025.json' -Raw
Invoke-RestMethod -Uri 'http://localhost:8000/v1/scenarios/simulate' -Method Post -ContentType 'application/json' -Body $scenario
```

The same scenario can run without HTTP: `python -m dtc.cli simulate --request examples/delhi_december_2025.json` after packaging a model.
`predict-official` writes monthly forecasts for the unlabelled August 2025–February 2026 period to the selected run's `predictions/official_monthly.csv`. It does not claim to fill the source workbook's missing **daily** `Guests` column.

## Run in containers

```powershell
docker compose build
docker compose run --rm api python -m dtc.cli train --config config/project.yaml
docker compose run --rm api python -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
docker compose run --rm api python -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
docker compose up api web
```

The compose services mount `data/` read-only and persist derived data and model runs under `artifacts/`. A Docker daemon must be running.

## Current validation result

The selected model uses last year's market demand adjusted by the change in allocated arriving seats, with an air-capacity elasticity of 0.75 selected using 2024 data. On a January–July 2025 holdout (310 complete market-month rows), monthly hotel check-ins have **18.82% WMAPE**, compared with **22.24%** for the seasonal-only baseline. The guest-day proxy has **18.83% WMAPE**. See [today's journal](journal/2026-10-09.md) and the versioned metrics under `artifacts/runs/` for details.

These scores measure the baseline forecast, not the causal effect of adding a flight. Scenario impacts use visible assumptions, including a 0.75 same-origin nationality share and a 0.80 nonresident visitor share. The data does not directly label passenger nationality, purpose of travel, or verified overnight guest nights.

## Data currently present

- `data/flight_data.xlsx`
- `data/data international_train.xlsx` and `data/data international_test.xlsx`
- `data/data domestic_train.xlsx` and `data/data domestic_test.xlsx`
- `data/Data_Dictionary.pdf`

The pipeline audits workbook schemas, dates, missing values, and row counts, and writes the results to `artifacts/processed/data_quality.json`. Origin-country to nationality allocation remains an explicit assumption because the data does not identify each traveller's nationality. The challenge brief describes additional reference data, but event, holiday, aircraft-type, and direct guest-night fields have not been found in the current pack. Competition data should stay within the permitted competition use. Do not commit or publish raw data without checking its license.

## Status

The training pipeline, scenario engine, API, and web app run locally. Docker files are present; container execution still needs verification on a host with an available Docker daemon. The final PDF and video have not been made.

Source: [official DCT challenge statement](https://challengeon.atrc.ae/en/challenges/atp2026/pages/dct-challenge-statement?lang=en), as supplied by the user.
