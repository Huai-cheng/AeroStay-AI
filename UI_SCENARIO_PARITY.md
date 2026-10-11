# Scenario dashboard parity contract

The project has two supported scenario dashboards:

1. `prototype/app.py` — Streamlit analytical dashboard.
2. `frontend/` — presentation-grade custom dashboard.

They are two clients of the same scenario service, not different products.

## Mandatory synchronization rule

Any scenario-control change must update **both dashboards at the same time**.
A scenario UI change is incomplete until all of the following agree:

- `prototype/api.py` request schema;
- `prototype/service.py` scenario behavior and `SCENARIO_CONTROL_KEYS`;
- `prototype/app.py` Streamlit controls;
- `frontend/src/components/scenario-app.tsx` custom controls;
- API and UI tests;
- `prototype/README.md` and `frontend/README.md`.

Neither dashboard may introduce a private scenario lever that the other does
not expose. Labels can be adapted to the interface, but units, defaults,
ranges, meaning, and request fields must remain equivalent.

## Canonical user-adjustable factors

| Factor | Existing route | New route | Canonical meaning |
| --- | --- | --- | --- |
| Route mode | Yes | Yes | Existing service change or proposed new service |
| Start and end date | Yes | Yes | Dates affected by the scenario |
| Departure origin | Yes | Yes | Aviation departure country |
| Target hotel nationality | Yes | Yes | Hotel market receiving allocated incremental arrivals |
| Weekly flights | Absolute scenario value | Absolute new-service value | Services per week |
| Seats per flight | Percentage change | Absolute seats | Aircraft/capacity assumption |
| Load factor | Percentage-point change | Absolute expected rate | Share of seats filled |
| Transfer share | Absolute rate | Absolute rate | Passengers connecting onward |
| Transit share | Absolute rate | Absolute rate | Passengers not entering the destination |
| Visitor share | Absolute rate | Absolute rate | Destination passengers considered visitors |
| Hotel-capture rate | Absolute rate | Absolute rate | Visitors expected to use hotels |
| Origin-to-nationality allocation | Absolute rate | Absolute rate | Incremental hotel arrivals assigned to the selected nationality |

## Canonical ranges

| Control | Range |
| --- | --- |
| Existing weekly flights | 0–1,000 |
| New-route weekly flights | 0–100 |
| Existing seats-per-flight change | −40% to +60% |
| New-route seats per flight | 50–600 |
| Existing load-factor change | −20 to +20 percentage points |
| New-route expected load factor | 30%–100% |
| Transfer share | 0%–90% |
| Transit share | 0%–25% |
| Visitor share | 20%–100% |
| Hotel-capture rate | 10%–100% |
| Origin-to-nationality allocation | 10%–100% |

Transfer share plus transit share must remain below 98%.

## Not user-adjustable

The following are calculated automatically and should be displayed as outputs,
diagnostics, or warnings rather than independent controls:

- total scheduled seats;
- scenario passenger movements;
- point-to-point passenger share;
- destination passengers;
- active/new/discontinued route counts;
- year-over-year capacity changes;
- origin-market seat concentration;
- calendar encodings, lag features, missing indicators, and model categories.

This separation prevents contradictory inputs and keeps the transparent chain:

```text
user controls → derived aviation flow → allocated hotel arrivals
              → pooled demand model → scenario guests / guest nights
```

## Sensitivity-analysis parity

Both dashboards expose the same two complementary diagnostics without adding
new scenario controls:

- **One-at-a-time stress test:** changes one lever around the submitted case and
  is easiest for a planner to explain.
- **SALib Morris global sensitivity:** varies all available levers across
  plausible local bounds, ranks overall influence with `mu_star`, and uses
  `sigma` to flag interaction or non-linearity.

Morris analysis is opt-in in both interfaces because it runs 72 full model
evaluations. The shared `/global-sensitivity` endpoint is authoritative; both
dashboards must display its ranking and meaning consistently.
