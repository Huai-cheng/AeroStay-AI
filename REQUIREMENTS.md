# Challenge requirements

This file records **what the prototype must demonstrate**. [DATA_AND_MODEL.md](DATA_AND_MODEL.md) covers how to model it; [SUBMISSION.md](SUBMISSION.md) covers what to upload.

## Problem and intended user

DCT Abu Dhabi planners need to estimate how changes to flight supply and passenger mix translate into hotel demand. Many arriving passengers transfer, return home, or stay with friends and family, so scheduled seats cannot be equated with hotel guests. The result must be useful for route discussions, seasonal hotel planning, and early warning about lost demand.

## Required capabilities and evidence

| ID | Requirement | Evidence in the finished prototype |
| --- | --- | --- |
| R1 | Change aviation and market factors and update hotel demand. | User controls produce an immediate baseline-versus-scenario comparison. |
| R2 | Show the entire seats-to-guest-nights conversion chain. | Each stage, formula, parameter, unit, and data source is visible; editable assumptions are clearly marked. |
| R3 | Back-test on held-out historical periods. | Report WMAPE with the test dates, target, aggregation grain, baseline comparator, and error breakdown. |
| R4 | Identify the most influential factors. | Show ranked scenario impacts or sensitivity analysis with the range used for each lever. |
| R5 | Break results down by source market and season. | Monthly/seasonal and market-level results, with totals that reconcile. |
| R6 | Explain the planning action in plain language. | A brief recommendation tied to the scenario and its uncertainty. |
| R7 | Document code, assumptions, and limitations. | Reproducible run instructions, assumption register, known gaps, and honest uncertainty. |
| R8 | Address incompatible country definitions. | Flight departure country and hotel nationality remain distinct; any crosswalk is explicit and uncertainty is shown. |

The prototype is the core deliverable. A concept-only presentation does not satisfy the brief.

## Scenario inputs

The application should support, where the supplied data permits:

- Adding a route from a previously unserved market or discontinuing an existing route.
- Changing weekly flight frequency, aircraft/seat capacity, or total scheduled seats.
- Changing load factor and the mix of origin markets.
- Changing transfer/transit share, visitor share or purpose mix, hotel-capture rate, and average length of stay.
- Selecting month/season; incorporating events, public holidays, and seasonality when data supports them.

For a new market without history, use an explicitly labelled comparable-market or pooled estimate and show a wider uncertainty range. Do not imply that a new-route estimate has been directly back-tested for that market.

## Scenario outputs

- Baseline, scenario, absolute change, and percentage change for hotel guest arrivals and guest nights.
- An inspectable waterfall for seats, arriving passengers, inbound visitors, hotel guests, and guest nights.
- Results by month/season and by **hotel nationality market**. Where relevant, also show the aviation departure-origin view separately.
- Leading drivers, uncertainty range, and warnings when inputs are outside observed history.
- A short planner-facing interpretation, for example an estimate of extra guest nights from a twice-weekly route and the assumptions on which it depends.

Occupancy may be shown only if defensible hotel room supply and the relationship between guest nights and room nights are available. Guest nights are **not** automatically occupied room nights.

## Judging priorities

| Criterion | Weight | Implication for the work |
| --- | ---: | --- |
| Technical accuracy and modelling rigour | 40% | Prioritize honest held-out validation, reconciliation, and correctly scoped claims. |
| Creativity and originality | 20% | Make the origin-to-nationality bridge and transparent scenario analysis useful to planners. |
| Practicality and realism | 20% | Keep controls, assumptions, and operating workflow credible. |
| Clarity | 20% | Show the chain, evidence, and decision in simple language. |

## Constraints and boundaries

- Use aggregated data only; no personal or passenger-level records.
- State all assumptions and show uncertainty where possible.
- Use the provided data within its competition license.
- The brief suggests Python, pandas/Polars, DuckDB, statsmodels, LightGBM/XGBoost, SALib, Streamlit/FastAPI, Plotly, and Docker. These are **options**, not individually mandatory requirements.
- Environmental responsibility is a stated challenge objective. A useful extension is to show incremental air capacity alongside incremental hotel demand, without making unsupported emissions claims.
