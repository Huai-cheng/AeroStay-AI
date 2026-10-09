# AeroStay AI — Abu Dhabi air-to-hotel demand simulator

A prototype for forecasting monthly international hotel demand and testing how a flight change might affect it. It includes a reproducible data pipeline, back-test, HTTP API, Streamlit dashboard, and Docker configuration.

**Important:** The demand forecast has been back-tested. The *causal effect* of adding or removing a flight has not. Treat scenario numbers as planning estimates with visible assumptions, not guaranteed bookings.

## Start here: clone and get the data

1. Clone this repository and run commands from its root directory:

   ```text
   git clone https://github.com/Huai-cheng/AeroStay-AI.git
   cd AeroStay-AI
   ```
2. Get the competition data from the team's shared Google Drive folder: **`[TEAM GOOGLE DRIVE FOLDER URL — TEAM LEAD: REPLACE THIS PLACEHOLDER]`**. Ask the team lead for access. Do not upload these files to this public GitHub repository; the challenge data is licensed for competition use only.
3. Download the six original files below. Keep their names and `.xlsx`/`.pdf` formats; do not convert, rename, or edit them. Put them directly in `data/`, not in a nested folder or ZIP archive. The Excel workbooks must contain a sheet named `Export`.

```text
data/
├── flight_data.xlsx
├── data international_train.xlsx
├── data international_test.xlsx
├── data domestic_train.xlsx
├── data domestic_test.xlsx
└── Data_Dictionary.pdf
```

`data/README.md` is already in Git. The six supplied files and all generated artifacts are ignored by Git. Every teammate needs their own authorized copy. The five workbooks are required by the current audit/training pipeline; the PDF is checked and is needed to interpret fields.

## Quick start without Docker

Requirements: Python **3.11+**, enough disk space for the input workbooks and generated files, and access to the six data files above. Run from the repository root. On Windows PowerShell:

```powershell
python -m venv .venv
& .venv\Scripts\python.exe -m pip install -e '.[test]'
& .venv\Scripts\python.exe -m dtc.cli audit --config config/project.yaml
& .venv\Scripts\python.exe -m dtc.cli train --config config/project.yaml
```

`train` prints a unique `run_id`. Copy that ID into the next two commands; evaluation and packaging are deliberately separate steps:

```powershell
& .venv\Scripts\python.exe -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
& .venv\Scripts\python.exe -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
& .venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux, create and activate the environment with `python3 -m venv .venv` and `source .venv/bin/activate`, then use `python -m pip install -e '.[test]'` and `python -m dtc.cli ...` for the same commands. You can also use the installed `dtc` command instead of `python -m dtc.cli`.

### Start the API and dashboard

Open **two terminals** in the repository root after packaging a model. In terminal 1:

```powershell
& .venv\Scripts\python.exe -m dtc.cli serve --config config/project.yaml
```

In terminal 2:

```powershell
& .venv\Scripts\python.exe -m streamlit run src/dtc/web.py --server.port 8501
```

Open the [dashboard](http://localhost:8501), enter a month and flight change, then select **Run scenario**. The [API documentation](http://localhost:8000/docs) lists the request fields. `GET http://localhost:8000/health` should report `"status": "ready"`; if it says `no_model`, finish `evaluate` and `package` first. The dashboard needs the API running.

## What the system does

```text
Original Excel files
  → audit and monthly ETL
  → explicit departure-origin to guest-nationality allocation
  → monthly feature table and chronological train/holdout split
  → model selection, back-test, and packaged baseline forecast
  → FastAPI ← Streamlit dashboard / terminal HTTP call
                 ↓
       scenario conversion chain and market-level results
```

The two country fields mean different things: a flight's **departure country** is not necessarily a hotel guest's **nationality**. The pipeline uses a documented allocation assumption; it does not identify each passenger. The scenario calculation makes this chain visible:

`scheduled seats → arriving passengers → point-to-point passengers → inbound visitors → hotel check-ins → estimated guest nights`

Load factor, transfer/transit share, visitor share, hotel capture, and stay length can be changed per scenario. New routes and reductions are represented by positive or negative changes in weekly flights. Results include a baseline, scenario, change, nationality breakdown, assumptions, a sensitivity table, and an illustrative range. The range is **not** a calibrated confidence interval.

## Data and training format

You do **not** create train/test CSVs by hand. Keep the source files in the format above. `train` runs these stages in order: `audit → prepare → map-markets → features → split → model selection`. Each stage also has its own CLI command (`audit`, `prepare`, `map-markets`, `features`, `split`) for debugging. `evaluate` scores the untouched holdout; `package` chooses the evaluated run for the API.

Flight records have `Date`, `Departure Country Name`, `Total Seats`, `Total PAX`, `Total Transfer`, `Total Transit`, and `Total P2P`. Hotel records have `Date`, `Nationality`, `New Arrivals`, and, in the labelled training workbook, `Guests`. The ETL aggregates them to **one row per month × guest nationality**. Representative columns in `artifacts/processed/train_features.csv` are:

| Role | Columns | Meaning |
| --- | --- | --- |
| Keys | `month`, `nationality` | Prediction unit. |
| Model inputs | `month_number`, `year_index`, `direct_origin_seats`, `allocated_origin_seats`, `citywide_seats`, `arrivals_same_month_last_year`, `allocated_seats_same_month_last_year`, `lag12_missing` | Calendar, air capacity, and historical demand. `nationality` is also an input. |
| Main label | `hotel_new_arrivals` | Monthly hotel check-ins, summed from `New Arrivals`. |
| Secondary observed measure | `guest_days` | Sum of daily `Guests`; **not verified overnight guest nights**. |
| Quality/partition | `missing_new_arrivals`, `observed_days`, `split` | Rows with missing daily arrivals are excluded from labelled training/evaluation. |

The chronological partitions are set in [`config/project.yaml`](config/project.yaml):

| Period | Use |
| --- | --- |
| 2022–2023 | Fit candidate models during selection. |
| 2024 | Choose among seasonal-only, seat-adjusted seasonal, Ridge regression, and XGBoost using WMAPE. |
| January–July 2025 | Held-out back-test, not used to choose the model. |
| August 2025–February 2026 | Official later-period monthly forecasts; the pipeline masks target columns and does not report an error without true labels. |

After the back-test, the serving reference is refitted through July 2025. Changing split dates or assumptions changes the experiment; rerun training, evaluation, and packaging. The current model only serves months present in the prepared data, not arbitrary future years.

## Model chosen and how to judge it

The selected baseline is **seat-adjusted seasonal**, not a Transformer or XGBoost. It starts with the same nationality's hotel check-ins in the same month last year, then adjusts that number when allocated arriving seats change. The selected air-capacity elasticity is **0.75**. A market median is used when last year's value is unavailable. XGBoost and Ridge were tested, but did not win on the 2024 selection period.

On the untouched January–July 2025 holdout, across **310 complete nationality-month rows**, the selected model had **18.82% WMAPE** for hotel check-ins; the seasonal-only baseline had **22.24%**. WMAPE here means `sum(abs(actual − predicted)) / sum(actual) × 100`; lower is better. Mean absolute error was about **940 check-ins per row**, and overall bias was **−4.84%** (underprediction). January's market-level WMAPE was **27.12%**, so performance varies by month. The guest-day proxy had **18.83% WMAPE**.

This is evidence that capacity helps predict the *baseline*. It does **not** validate the causal uplift from a new route. The nationality bridge, nonresident visitor share, route displacement, and overnight-night definition need better evidence before using the output for high-stakes commitments. Inspect `metrics/by_month.csv` and `metrics/by_market.csv`, not only the headline error.

## Predictions and scenarios from a terminal

Without starting a server, use the selected packaged run:

```powershell
& .venv\Scripts\python.exe -m dtc.cli predict --month 2025-12
& .venv\Scripts\python.exe -m dtc.cli simulate --request examples/delhi_december_2025.json
& .venv\Scripts\python.exe -m dtc.cli predict-official
```

The example scenario adds **two weekly Delhi flights**, with **200 seats per flight** and **80% load factor**, in December 2025. Edit a copy of that JSON to test another month, origin, frequency, seat count, or optional rate. A negative `flights_per_week_delta` removes service; it cannot remove more seats than the observed origin capacity.

With the API running, PowerShell can call it directly:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/v1/predict' -Method Post -ContentType 'application/json' -Body '{"month":"2025-12"}'
$scenario = Get-Content -LiteralPath 'examples/delhi_december_2025.json' -Raw
Invoke-RestMethod -Uri 'http://localhost:8000/v1/scenarios/simulate' -Method Post -ContentType 'application/json' -Body $scenario
```

These endpoints return monthly totals and guest-nationality results. `predict-official` writes monthly forecasts to `predictions/official_monthly.csv`; it does not fill the source workbook's missing **daily** `Guests` column.

## Run with Docker Compose

Requires a working Docker engine. From the repository root, after downloading data:

```powershell
docker compose build
docker compose run --rm api python -m dtc.cli train --config config/project.yaml
docker compose run --rm api python -m dtc.cli evaluate --config config/project.yaml --run-id YOUR_RUN_ID
docker compose run --rm api python -m dtc.cli package --config config/project.yaml --run-id YOUR_RUN_ID
docker compose up api web
```

Then use [Streamlit on port 8501](http://localhost:8501) and [API docs on port 8000](http://localhost:8000/docs). Compose mounts `data/` read-only and `artifacts/` for persistent outputs. `docker compose config --quiet` passed, but a full image build/run has **not** yet been verified because Docker was unavailable on the development host. If the engine is not running, use the local Python path above.

## Configuration and output locations

[`config/project.yaml`](config/project.yaml) controls input filenames, split dates, candidate elasticities, market assumptions, output paths, and service ports. Raw workbooks remain unchanged. Main generated outputs:

```text
artifacts/
├── processed/
│   ├── data_quality.json
│   ├── air_origin_month.csv
│   ├── hotel_nationality_month.csv
│   ├── market_allocation_assumption.csv
│   ├── market_month_features.csv
│   ├── train_features.csv
│   ├── validation_features.csv
│   └── official_test_features.csv
├── runs/<run_id>/
│   ├── manifest.json                # model, periods, code/input hashes
│   ├── metrics/                     # selection, summary, month, market
│   ├── predictions/                 # holdout and official monthly forecasts
│   ├── model/                       # model/reference/fallback data
│   └── reports/                     # audit, split, allocation assumption
└── selected.json                    # run used by API and dashboard
```

These files are generated locally and excluded from Git. Each teammate can reproduce them from authorized data. See [`DATA_AND_MODEL.md`](DATA_AND_MODEL.md) for data caveats, [`ARCHITECTURE.md`](ARCHITECTURE.md) for contracts, and [`journal/2026-10-09.md`](journal/2026-10-09.md) for decisions and the measured run.

## Common problems

- **Missing file or `Export` sheet:** check exact names, formats, and location under `data/`; run `python -m dtc.cli audit`.
- **`no_model` from `/health`:** run `train`, then `evaluate` with its printed run ID, then `package` with the same ID.
- **Dashboard cannot reach API:** start the API first and check port 8000; with Compose, start both services using `docker compose up api web`.
- **No rows for a month:** the month must exist in the prepared flight/hotel tables; this prototype does not generate future schedule data.
- **Metrics changed:** confirm the data files and YAML are the same; each run records input and code hashes in `manifest.json`.

## Project documents and submission status

[`REQUIREMENTS.md`](REQUIREMENTS.md) lists challenge criteria; [`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) defines the planner workflow; [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) records remaining work; [`SUBMISSION.md`](SUBMISSION.md) plans the 10-page PDF and 1–2 minute video. The prototype works locally, but the final PDF/video, causal scenario validation, and Docker runtime verification remain open.

Challenge brief: [DCT Abu Dhabi challenge statement](https://challengeon.atrc.ae/en/challenges/atp2026/pages/dct-challenge-statement?lang=en).
