# AeroStay Intelligence — exact presentation content specification

## Document status

- Deliverable: 10-page, 16:9 presentation exported as PDF from an editable PPTX.
- Audience: DCT Abu Dhabi challenge judges and tourism planners.
- Deck role: explain the problem, feature engineering, modelling evidence,
  scenario design and real-world use.
- Video role: demonstrate the working product and scenario interaction.
- Speaker notes: none. The PDF must contain every definition, caveat and source
  required to understand or verify the conclusions.
- Visual direction: dark indigo DCT-inspired background, lavender structure,
  teal selected-result accent, amber assumptions and muted grey-blue baselines.

## Approval states

| Page | Subject | Status |
| ---: | --- | --- |
| 1 | Cover | Provisionally approved; final UI visual pending |
| 2 | Problem and planning gap | Approved by delegated decision |
| 3 | System and conversion chain | Approved |
| 4 | Feature-role framework | Approved |
| 5 | Final model features | Approved; simplified for judges |
| 6 | Scenario factors and exclusions | Approved |
| 7 | Feature experiment evidence | Approved |
| 8 | Loss-function evidence | Approved |
| 9 | Final model performance | Approved with complete evaluation-coverage line |
| 10 | Product use and implementation | Text approved; final UI capture pending |

---

# Page 1 — Cover

## Approval status

Provisionally approved. Text is locked. The product-interface visual will be
selected after the UI is finalized.

## Exact on-slide copy

**Upper label**

```text
DCT ABU DHABI CHALLENGE
```

**Title**

```text
AeroStay Intelligence
```

**Subtitle**

```text
Estimating how flight-plan changes affect Abu Dhabi hotel demand
```

**Supporting line**

```text
An explainable scenario simulator connecting aviation supply to hotel guest nights
```

**Team identification**

```text
Huaicheng Su · Arjun Kuttikkat · Alreem Alzaabi
```

**Date**

```text
2026
```

## Layout and visual

- Text occupies the left 52% of the slide.
- A reserved product-interface crop occupies the right 44%.
- Use a perspective crop or device-free browser crop, not a laptop mockup.
- The interface visual must show the scenario decision and result, rather than
  a form with empty fields.
- Until the UI is final, use a labelled placeholder in internal drafts only.
- No model metric or architecture diagram appears on the cover.

## Open item

- Final UI screenshot and crop.

---

# Page 2 — Planning gap

## Approval status

Approved by delegated content decision.

## Exact on-slide copy

**Title**

```text
Flight decisions and hotel-demand forecasts remain disconnected
```

**Explanation**

```text
Most international visitors reach Abu Dhabi by air, but only a share of
arriving passengers stay in the city’s hotels.

Some passengers transfer to another flight. Others transit without entering
the destination, live locally, stay with friends or family, or use other
accommodation.

Flight capacity therefore influences hotel demand through several conversion
steps rather than through a fixed seats-to-guests ratio.
```

**Planning gap**

```text
Air-service and hotel-demand planning currently use separate forecasts.
Without a shared conversion model, planners cannot quickly quantify how a
proposed flight change could affect hotel guest nights.
```

**Decision questions**

```text
How many hotel guest nights could a new twice-weekly route generate?

What happens when an existing route changes its weekly flights, seats per
flight or expected load factor?
```

## Main visual

One editable horizontal diagram:

```text
AVIATION PLAN              UNKNOWN CONVERSION              HOTEL PLAN

Routes                                                     Nationality demand
Weekly flights       ─────        ?        ─────            Seasonal demand
Seat capacity             Transfer / transit               Hotel guest nights
Load factor               Visitor share                    Capacity planning
                          Hotel-capture rate
                          Market allocation
```

## Format

- Title: 31–33 pt.
- Explanation and planning gap: 18 pt.
- Diagram group labels: 18–20 pt bold.
- Diagram details: 15–16 pt.
- Decision questions: 17–18 pt in lavender.
- Unknown-conversion labels: amber.
- No photograph or model metric.

## Source

Visible footer:

```text
Source: DCT Abu Dhabi Challenge Statement
```

---

# Page 3 — Model architecture

## Approval status

Approved. The architecture follows the challenge’s transparent-parametric plus
machine-learning design. The judge-facing product has one primary output:
estimated hotel guest nights.

## Exact on-slide copy

**Title**

```text
Two-layer model architecture
```

**Subtitle**

```text
A transparent conversion layer turns flight-plan changes into hotel-arrival
signals. Pooled Poisson XGBoost learns the demand response.
```

**Architecture**

```text
SUPPLIED HOTEL DATA                           SUPPLIED FLIGHT DATA
Guests, new arrivals, same-day guests,        Routes, frequency, seats,
hotel nationality and segment                 passenger composition
                         ↓
DATA ETL
Validate source grain · preserve missingness · create calendar and
leakage-safe prior-year features · build scenario-ready aviation tables
                         ↓
               TWO CONNECTED LAYERS

LAYER 1 · TRANSPARENT CONVERSION
Flight plan
Scheduled seats
Passenger movements
Destination passengers
Estimated visitors
Estimated hotel arrivals
Incremental new arrivals for the selected hotel market

LAYER 2 · POOLED POISSON XGBOOST
Calendar and trend
Hotel nationality and domestic/international segment
Current hotel flow and missingness
Prior-year demand
Scenario-adjusted new arrivals

Training target: supplied hotel guests
Objective: count:poisson

                         ↓
ESTIMATED HOTEL GUEST NIGHTS
Change from baseline
Breakdown by month and hotel nationality
```

**Model bridge**

```text
The transparent conversion layer feeds the model through scenario-adjusted new
arrivals. The two layers do not produce separate forecasts and are not averaged.
```

**Visible limitation**

```text
Estimated hotel guest nights = max(predicted hotel guests − same-day guests, 0)

Average length of stay and room-night records are not supplied. AeroStay does
not claim to predict hotel occupancy or occupied rooms.
```

## Format

- One editable model architecture with two clearly labelled layers.
- White represents observed or proposed values.
- Amber represents explicit assumptions.
- Lavender represents derived conversion values.
- Teal represents modelled output.
- A thin sensitivity loop indicates that one-at-a-time and SALib Morris analyses
  rerun both layers.

## Source

Visible footer: `Source: supplied hotel and flight data; AeroStay scenario engine`.
Repository evidence: `prototype/scenario_engine.py`, `prototype/service.py`,
`prototype/modeling.py`.

---

# Page 4 — Feature-engineering framework

## Approval status

Approved.

## Exact on-slide copy

**Title**

```text
Each candidate variable received one defined role
```

**Subtitle**

```text
Business meaning and forecast-time availability came before model performance.
```

**Main table**

| Role | Decision question | Examples | Treatment |
| --- | --- | --- | --- |
| Model feature | Is it known before prediction, semantically valid and useful in chronological evaluation? | Seasonality, hotel nationality, new arrivals, same-day activity, prior-year demand | Included in pooled Poisson XGBoost |
| Scenario factor | Can a planner intentionally change it for a route or capacity scenario? | Weekly flights, seats per flight, load factor, transfer share, transit share | Exposed in both dashboards and processed by the conversion layer |
| ETL transformation or check | Does it standardize data, derive safe values or prevent invalid inputs? | Date and grain normalization, missing-value handling, ratio recomputation, reconciliation and range checks | Applied automatically before training and simulation |
| Excluded or deferred | Is it redundant, incomplete, unavailable at prediction time, semantically invalid or unstable out of time? | Cabin-class splits, future realized passengers, target lags, exact origin-to-nationality matching | Excluded with a recorded reason and condition for retesting |

**Selection sequence**

```text
Business meaning → forecast-time availability → valid entity and time semantics
→ leakage check → rolling chronological validation → held-out confirmation
→ final role
```

**Highlighted conclusion**

```text
A useful planning factor does not have to become a model column.

Weekly flights and passenger composition remained valuable scenario controls
even when they failed the final model-selection test.
```

## Source

Visible footer: `Source: AeroStay feature registry and chronological experiment protocol`.

---

# Page 5 — Final model features

## Approval status

Approved with coverage percentages and detailed data-audit information removed
from the slide.

## Exact on-slide copy

**Title**

```text
The final model uses 14 carefully selected inputs
```

**Subtitle**

```text
The features describe when demand occurs, which market it belongs to, current
hotel activity and historical context.
```

| Feature category | Inputs | What they tell the model |
| --- | --- | --- |
| Time and season | Linear time trend; annual seasonal sine and cosine; weekend indicator; month; day of week | Position in the long-term, annual and weekly demand cycle |
| Market context | Hotel nationality; domestic/international segment | Which demand pattern the observation belongs to |
| Current hotel activity | New guest arrivals; same-day guests; same-day missing indicator | Current visitor flow and whether same-day information is available |
| Historical context | Previous-year guests; previous-year arrivals; year-over-year arrival ratio | Comparable prior season and direction of demand growth |

**Feature count**

```text
14 inputs
10 numeric · 4 categorical
```

**Highlighted conclusion**

```text
The model receives the scenario through adjusted new arrivals. It does not need
every upstream aviation factor as another model input.

Flight frequency, seat capacity and passenger composition remain in the
transparent scenario layer.
```

**Single engineering example**

```text
The year-over-year arrival ratio gives XGBoost relative demand growth without
requiring it to reconstruct the ratio from two separate values.
```

## Source

Visible footer: `Source: final B0 pooled Poisson feature definition`.
Coverage percentages, imputation details and complete ablation tables remain in
the project evidence files and are intentionally omitted from the presentation.

---

# Page 6 — Scenario controls and deliberate exclusions

## Approval status

Approved.

## Exact on-slide copy

**Title**

```text
Scenario controls and deliberate feature exclusions
```

**Subtitle**

```text
Operational levers drive the transparent conversion layer. Redundant or
unreliable fields stay outside the model.
```

**Scenario conversion**

```text
Weekly flights × seats per flight
Scheduled seats × expected load factor
Passenger movements × (1 − transfer share − transit share)
Destination passengers × visitor share
Estimated visitors × hotel-capture rate
Estimated hotel arrivals × nationality allocation
Scenario-adjusted new arrivals
```

**Cabin-class exclusion**

```text
Economy, business and first-class fields were considered explicitly.

We excluded them because the available cabin splits were incomplete, closely
related to total capacity or passenger volume, and did not yet show reliable
additional value.

Retest when consistent future cabin-level schedules and passenger forecasts
become available.
```

**Other exclusion examples**

| Excluded candidate | Reason |
| --- | --- |
| Future realized passengers and load factor | Unknown when the forecast is produced; would leak future operational results |
| Exact origin-to-nationality match | Departure country and hotel nationality describe different concepts |
| Short guest-target lags | Long horizon would require recursive predictions and compound error |

**Bottom distinction**

```text
Scenario-only means the factor remains operationally important. Excluded means
the available field could not enter the model honestly or reliably.
```

## Source

Visible footer: `Source: DCT conversion requirements and AeroStay feature decisions`.

---

# Page 7 — Feature experiment evidence

## Approval status

Approved.

## Exact on-slide copy

**Title**

```text
More aviation features improved validation but failed the held-out test
```

**Subtitle**

```text
Chronological confirmation prevented us from selecting a more complex but less
reliable feature set.
```

**Experiment scope**

```text
67 feature definitions · 2 rolling folds · 134 chronological fits
```

**Comparison**

| Model | Rolling validation WMAPE | Held-out WMAPE |
| --- | ---: | ---: |
| Selected 14-input baseline | 11.87% | 12.99% |
| Baseline + weekly flight frequency + network seat concentration | 11.70% | 13.10% |

**Decision**

```text
Retain the original 14-input pooled Poisson feature set.

Weekly flight frequency and seat concentration remain useful for scenario
analysis and reporting, but the held-out result did not support adding them to
the production model.
```

## Visual

Two editable horizontal dumbbell charts. The challenger wins the rolling
validation panel and loses the held-out panel. Label both panels “Lower is
better”.

## Source

Visible footer: `Source: pooled Poisson feature search; chronological rolling validation and 2024-08-01 to 2025-02-28 holdout`.

---

# Page 8 — Loss-function selection

## Approval status

Approved.

## Exact on-slide copy

**Title**

```text
Poisson provided the best overall count forecast
```

**Subtitle**

```text
We compared direct regression, log-transformed regression and count-specific
learning using the same baseline feature definition.
```

| Loss treatment | Held-out WMAPE | Interpretation |
| --- | ---: | --- |
| Poisson count loss | 12.99% | Learns nonnegative guest counts directly |
| Log-target squared error | 13.00% | Reduces domination by the largest observations |
| Direct squared error | 13.50% | Penalizes large absolute errors strongly |

**Cross-entropy diagnostic**

```text
Binned cross entropy · 47.23% WMAPE

Converting guest counts into ranges removed count precision and produced large
underprediction. Rejected as a forecasting loss.
```

**Decision**

```text
Selected: pooled Poisson XGBoost

Poisson achieved the lowest overall WMAPE, respects the nonnegative count
target and provides one consistent model for domestic and international demand.
```

**Qualification**

```text
Log target remained a strong benchmark and performed slightly better for
international demand, but Poisson produced the strongest single pooled result.
```

## Source

Visible footer: `Source: common chronological holdout, 2024-08-01 to 2025-02-28`.

---

# Page 10 — Product workflow and implementation

## Approval status

Text approved. Final screenshot and displayed scenario values remain pending
until the interface is finalized and reconciled.

## Exact on-slide copy

**Title**

```text
From flight scenario to hotel-demand decision
```

**Subtitle**

```text
A planner can change the flight plan, review estimated hotel guest nights and
test which assumptions drive the result.
```

**Workflow**

```text
1 · DEFINE THE SCENARIO
Choose an existing or proposed route, planning period, departure origin and
target hotel nationality.

2 · ADJUST THE ASSUMPTIONS
Change weekly flights, seats per flight, load factor, transfer and transit
shares, visitor share, hotel-capture rate and market allocation.

3 · REVIEW THE DECISION OUTPUT
Compare estimated hotel guest nights with the baseline and inspect the monthly
and nationality breakdown.
```

**Decision safeguards**

| Safeguard | Meaning |
| --- | --- |
| Conversion reconciliation | Seats, passengers, visitors and hotel arrivals remain mathematically consistent |
| One-at-a-time stress test | Shows the effect of changing one assumption around the current scenario |
| SALib Morris sensitivity | Varies all controls together and ranks overall influence and interaction |
| Range and uncertainty warnings | Flags unseen routes, unsupported values and assumptions requiring caution |

**Implementation path**

```text
PROTOTYPE
Supplied hotel and flight data

PLANNING PILOT
Official schedules, forecast load factors and reviewed conversion assumptions

OPERATIONAL USE
Regular data refresh, back-testing, assumption governance and model monitoring
```

**Future data**

```text
Authoritative average length of stay, event calendars and source-market
holidays can replace current assumptions when available.
```

**Shared product rule**

```text
Streamlit and the custom dashboard use the same scenario controls and shared
model service.
```

**Closing line**

```text
One model. Visible assumptions. A decision the planner can challenge.
```

## Visual

- One large final interface screenshot, without a device frame.
- The screenshot must show scenario controls, estimated hotel guest nights,
  change from baseline and the monthly comparison.
- Do not capture empty, loading, warning or developer states.
- Drafts use an internal placeholder only; the submitted PDF cannot contain it.

## Source

Visible footer: `Source: AeroStay live scenario prototype`.

---

# Page 9 — Final model performance

## Approval status

Approved. WMAPE remains the primary comparison metric. A compact coverage line
names the complete evaluation framework without placing every value in the main
table.

## Exact on-slide copy

**Title**

```text
Pooled Poisson reduced overall error by 41% versus linear regression
```

**Subtitle**

```text
The selected model delivered the strongest combined result while retaining one
consistent estimator for domestic and international demand.
```

| Model | Overall WMAPE | Domestic WMAPE | International WMAPE |
| --- | ---: | ---: | ---: |
| Selected pooled Poisson XGBoost | 12.99% | 7.64% | 16.24% |
| Lean pooled Poisson XGBoost | 13.22% | 6.45% | 17.34% |
| Ridge linear regression | 21.84% | 8.82% | 29.75% |

**Interpretation**

```text
The lean model performed better domestically, but the selected feature set
improved international demand enough to produce the strongest combined result.
```

**Two complementary metrics**

```text
Aggregate bias        +2.73%
Macro-market WMAPE    19.99%
```

```text
Bias shows whether total demand is systematically over- or underpredicted.
Macro-market WMAPE gives each hotel nationality equal importance.
```

**Evaluation coverage**

```text
Forecast accuracy: WMAPE · bias · MAE · RMSE
Market fairness: macro and 90th-percentile market WMAPE
Seasonal stability: monthly WMAPE and monthly bias
Scenario validity: reconciliation · monotonic response · range warnings · uncertainty
```

**Metric clarification**

```text
Offline metrics score the supplied hotel Guests target. Estimated guest nights
are derived afterward by removing same-day guests.
```

## Source

Visible footer: `Source: common chronological holdout, 2024-08-01 to 2025-02-28`.
