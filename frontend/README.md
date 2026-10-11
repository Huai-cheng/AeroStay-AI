# AeroStay judge experience

This is the presentation-grade Next.js interface for the selected pooled Poisson XGBoost prototype. The Streamlit app remains available as an internal analytical workbench; this interface is the intended judging experience.

## Run locally

From the repository root, start the model API:

```powershell
& .venv\Scripts\python.exe -m uvicorn prototype.api:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Terminal checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/model/metrics
```

A scenario request:

```powershell
$body = @{
  mode = 'Existing route'
  origin_country = 'INDIA'
  target_nationality = 'INDIA'
  start_date = '2025-08-01'
  end_date = '2026-02-28'
  scenario_weekly_flights = 16.3
  visitor_share = 0.75
  hotel_capture_rate = 0.65
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:8000/simulate -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod http://127.0.0.1:8000/sensitivity -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod http://127.0.0.1:8000/global-sensitivity -Method Post -ContentType 'application/json' -Body $body
```

## What the UI is designed to prove

- The opening is a scroll-controlled, four-chapter journey from aircraft to arrivals to hotel to decision. See [STORYBOARD.md](STORYBOARD.md) for the visual sequence and asset prompts.
- Existing routes use origin-specific observed baselines.
- Proposed routes are visibly labelled as analog estimates and receive a wider planning range.
- The six-stage conversion chain separates observed values, assumptions, and model output.
- The stress test reruns the full model path for each perturbation.
- The opt-in SALib Morris panel varies all levers together and separates overall
  influence (`mu_star`) from interaction/non-linearity (`sigma`).
- Model choice, chronological holdout, WMAPE, feature groups, and non-causal limitations stay visible to judges.

The visual sequence uses illustrative imagery and accessible HTML. Exact analytical quantities remain in the live result and ECharts panels.

## Dashboard parity requirement

The custom dashboard and Streamlit dashboard must expose the same scenario
factors, units, defaults, ranges, and API semantics. A scenario-control change
must update both dashboards at the same time. See the authoritative
[scenario dashboard parity contract](../UI_SCENARIO_PARITY.md).
