# DCT flight-to-hotel scenario prototype

This is an isolated interactive prototype built from the supplied raw data and the
official challenge requirements. It does not import or inspect the repository's
pre-existing solution.

## Train the selected model

```powershell
.\.venv\Scripts\python.exe -m prototype.train_models
```

## Launch the application

```powershell
.\.venv\Scripts\python.exe -m streamlit run prototype\app.py
```

Or use the one-command launcher, which trains the model automatically if artifacts are missing:

```powershell
.\prototype\run.ps1
```

The application uses the selected **B0 pooled Poisson XGBoost**: one estimator is
fitted across domestic and international rows, with the segment retained as a
categorical feature. Its Poisson objective matches the non-negative count target.
The scenario engine remains a transparent parametric layer, as required by the
challenge.

## Target and output

- Model target: supplied daily `Guests`.
- Guest-night output: predicted `Guests - Same-Day Guests`.
- Missing international same-day values are treated as uncertain and are identified
  explicitly in the interface.

## Important limitation

The local data does not contain visitor share, hotel-capture rate, average length of
stay, events, public holidays, aircraft type, occupancy, or room supply. The relevant
conversion factors are exposed as assumptions rather than represented as observed data.

## Sensitivity analysis

The decision view includes a quick one-at-a-time stress test and an opt-in
SALib Morris global-sensitivity analysis. Morris varies all scenario levers
together across plausible bounds and reports `mu_star` (overall influence) and
`sigma` (interaction or non-linearity). It runs through the same conversion
chain and trained model as the central scenario; it is not a separate forecast.

## Dashboard parity requirement

Streamlit and the custom dashboard must expose the same scenario factors, units,
defaults, ranges, and API semantics. A scenario-control change must update both
dashboards at the same time. The authoritative checklist and maintenance rule are
in [UI_SCENARIO_PARITY.md](../UI_SCENARIO_PARITY.md).
