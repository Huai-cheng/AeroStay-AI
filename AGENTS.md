# Repository instructions for AI coding agents

## Mandatory scenario-dashboard parity

This repository has two supported scenario dashboards:

- `prototype/app.py` — Streamlit dashboard.
- `frontend/src/components/scenario-app.tsx` — custom Next.js dashboard.

They are two clients of one scenario product. **Any change to scenario inputs,
labels, defaults, ranges, validation, units, request fields, or user-visible
scenario behavior must update both dashboards in the same task.** Do not edit
one scenario dashboard and leave the other inconsistent.

For every scenario-control change, verify and update as applicable:

1. `prototype/api.py` and `prototype/service.py`;
2. `prototype/app.py`;
3. `frontend/src/components/scenario-app.tsx` and its types/styles;
4. API/UI tests;
5. `prototype/README.md`, `frontend/README.md`, and
   `UI_SCENARIO_PARITY.md`.

Before finishing, compare both dashboards against the canonical control list in
`prototype.service.SCENARIO_CONTROL_KEYS` and the ranges in
`UI_SCENARIO_PARITY.md`. A scenario UI change is incomplete until parity is
restored and both Python tests and frontend checks pass.

