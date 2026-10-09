# Implementation plan

This sequence turns the brief into a testable prototype. [ARCHITECTURE.md](ARCHITECTURE.md) defines the planned CLI, API, YAML, Docker, and output contracts. Each stage below should finish with a working command and an inspectable artifact.

## 0. Create the runnable project skeleton

- Add the Python package, pinned dependencies, configuration loader and validator, CLI command tree, API skeleton, Dockerfile, and `compose.yaml`.
- Make `audit`, `prepare`, `train`, `evaluate`, and `serve` callable from a terminal, even if some initially report a clear “not implemented” error.
- Add a unique run-ID convention and output manifest. Keep competition input files read-only.

Exit condition: a fresh container starts, the API health endpoint responds, and the CLI reads `config/project.yaml` with helpful validation errors.

## 1. Audit and prepare the supplied pack

- Read `data/Data_Dictionary.pdf` and inspect every workbook sheet.
- Record field names, units, dates, grain, and caveats; identify which files contain passenger and hotel targets.
- Check join coverage, aggregate totals, missing markets, and the train/test chronology.
- Implement separate `audit`, `prepare`, `map-markets`, and `features` stages. Produce air-origin and hotel-nationality monthly tables without rewriting source files.
- Check that 2022 monthly flight rows and 2023-onward daily rows become comparable monthly totals.

Exit condition: documented schema and reconciled monthly totals, or an explicit list of missing data that limits the model.

## 2. Establish the reference forecast

- Build a seasonal-naive benchmark and the transparent conversion chain.
- Define parameter estimates and origin-to-nationality mapping from evidence, with fallback assumptions clearly labelled.
- Run time-ordered validation; report WMAPE and bias for observed monthly hotel check-ins and guest-days. Report estimated guest nights separately until their observed definition is verified.

Exit condition: held-out predictions and error table that can be reproduced from the raw files.

## 3. Improve the model where evidence supports it

- Fit a regression reference model, then test XGBoost conversion effects with seasonality and market effects.
- Retain it only if it improves held-out results and behaves sensibly under scenario changes.
- Quantify uncertainty, including the origin-to-nationality crosswalk and unseen-route estimates.

Exit condition: selected model documented against the reference forecast, including any markets where it performs poorly.

## 4. Build the simulator

- Implement the scenario engine as a callable Python module before adding the API and web interface.
- Implement controls for route, frequency, seats, load factor, traveller mix, hotel capture, length of stay, and date.
- Serve the same packaged model through `POST /v1/scenarios/simulate` and the web app. Validate requests and record model/assumption versions.
- Show stage-by-stage calculations, baseline versus scenario, market/season breakdowns, uncertainty, and driver ranking.
- Add input checks for impossible values and warnings for scenarios beyond historical support.
- Provide a plain-language planner takeaway based on the displayed result.

Exit condition: a user can reproduce at least these demonstrations: a new twice-weekly route, a winter frequency reduction, and a load-factor or seat-capacity change. Equivalent CLI, API, and app inputs give equivalent outputs.

## 5. Package and communicate

- Finish documented terminal training, evaluation, and HTTP prediction commands. Verify them in a fresh Docker build.
- Store model files, resolved YAML, metrics, holdout predictions, and provenance in `artifacts/runs/<run_id>/`.
- Create the [ten-page PDF and 1–2 minute video](SUBMISSION.md) from the working prototype and actual validation results.
- Verify every headline number in the presentation against a reproducible run.

Exit condition: a reviewer can start the prototype, change a lever, inspect assumptions, see validation evidence, and follow the demo without the authors present.

## Decisions that depend on data inspection

- Whether hotel nationality and flight departure origin can be linked from supplied aggregate evidence.
- How daily `Guests` and `Same-Day Guests` relate to verified overnight guest nights.
- How to estimate resident/visitor share, hotel capture, and length of stay from the current pack or labelled assumptions.
- Whether occupancy is defensible as an output; hotel room supply is not in the current files.
- Whether the candidate XGBoost layer improves the held-out result enough to ship. The transparent chain and simple benchmark remain regardless.
