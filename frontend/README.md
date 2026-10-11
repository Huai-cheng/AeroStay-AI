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

## Structure

- `/` has two full-screen sections. On desktop they snap: a small scroll moves
  between the landing and the simulator. On narrow screens they stack normally.
  - **Landing:** a dot-matrix world map (Natural Earth 1:50m, projection
    centred on Abu Dhabi). Every served origin is drawn as a great-circle route
    from its main gateway city, and the selected origin country is highlighted.
    Aircraft depart at a rate that grows with the scenario's weekly flights.
    Each landing releases passengers split into hotel guests, other arrivals
    and onward connections, in the proportions the API's conversion chain
    returns. The map re-frames itself so the selected route never sits under
    the headline. It also shows the live headline result.
  - The map dots come from `src/lib/world-dots.json`; rebuild that file with
    `node scripts/build-world-dots.mjs`.
  - **Simulator:** a scrollable control sidebar and a results view. Results
    update automatically about 0.2 s after any change; stale requests are
    cancelled. The views are the headline change, the conversion funnel, the
    monthly change, and quick or full (SALib Morris) sensitivity.
- `/how-it-works` holds the scroll story (see [STORYBOARD.md](STORYBOARD.md)),
  the conversion chain, the model, live back-test metrics, the sensitivity
  methods and the limitations.

## Accuracy notes

- Every number shown comes from the API response; the page never recalculates
  model outputs.
- The planning range from `/simulate` covers **all Abu Dhabi hotels**, and is
  labelled that way.
- The monthly chart shows scenario minus baseline guest nights for all hotels.
  Only the selected nationality's arrivals change, so this equals the selected
  market's change.

The route map and skyline are illustrative. Exact quantities are in the result
panels.

## Dashboard parity requirement

The custom dashboard and Streamlit dashboard must expose the same scenario
factors, units, defaults, ranges, and API semantics. A scenario-control change
must update both dashboards at the same time. See the authoritative
[scenario dashboard parity contract](../UI_SCENARIO_PARITY.md).
