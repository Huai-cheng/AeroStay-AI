# Product requirements: Abu Dhabi flight-to-hotel simulator

## 1. Product goal

Give a DCT Abu Dhabi planner a quick, understandable estimate of how a proposed change to arriving flights could affect international hotel demand by month and guest nationality.

The prototype must answer a concrete question such as: “If a route gains two flights per week in December, how many additional hotel check-ins and guest nights might result, and which assumptions drive that estimate?”

## 2. Intended user and decision

**Primary user:** A tourism or aviation planner who discusses routes, airline capacity, events, and hotel planning. The user does not need to know Python or machine learning.

**Decision supported:** Compare flight plans, identify markets and seasons with meaningful demand changes, and decide which route or capacity proposals deserve closer investigation.

The simulator estimates a planning scenario. It does not claim that every additional passenger is a new visitor or that an observed association proves a route caused hotel demand.

## 3. First release: one guided workflow

1. Select a month or season and view the current flight-plan baseline.
2. Select a route or create a proposed new route.
3. Change flights per week, seats per flight, or load factor. Optionally change transfer share, visitor share, hotel conversion, and length of stay in an **Assumptions** panel.
4. See baseline and scenario results update together.
5. Inspect the calculation chain, market breakdown, uncertainty, and the strongest drivers.
6. Export a short scenario summary for discussion.

The initial screen should make one example scenario available so a reviewer can understand the product without preparing inputs.

## 4. Information architecture and screen content

### A. Scenario builder

Left panel: month/season, departure country and city, route status, flights per week, seats per flight, and load factor. Show units and the historical baseline next to every changed input. For an unseen route, label the rate assumptions as comparable-market estimates.

An expandable **Assumptions** area contains transfer/transit share, nonresident visitor share, origin-to-nationality allocation, hotel conversion, and average stay. Display the source or estimation method beside each value. Prevent impossible shares and negative capacity.

Aircraft type is not in the current flight workbook. In the first release, change seats per flight directly; add an aircraft selector only if a verified aircraft-to-seat reference table is obtained. The current pack also lacks the promised event and holiday tables, so do not show them as functioning controls until data is available.

### B. Results overview

At the top, show **baseline**, **scenario**, and **change** for estimated hotel check-ins and estimated guest nights, each with an uncertainty range. Make the selected month and scope visible.

Below, show a five-stage flow:

`arriving seats → arriving passengers → point-to-point passengers → estimated hotel guests → estimated guest nights`

The user can click a stage to see its formula, rate, data source, and scenario override. Explain that point-to-point passengers can still include residents and people who do not stay in hotels.

### C. Market and season detail

Show a monthly trend and a table by **guest nationality**. Columns: baseline, scenario, change, percentage change, and uncertainty. If a chart refers to flight **departure country**, label that separately; never call it guest nationality. Totals in the table must equal the headline total.

### D. Drivers and explanation

Show the effect of changing one lever at a time over a stated range. Rank the levers by change in estimated guest nights. Add a brief plain-language takeaway, such as: “The estimate is most sensitive to the share of arriving passengers who stay in hotels.”

### E. Validation and limitations

Show the historical periods used for training and back-testing, the seasonal benchmark, WMAPE and bias, and errors by month and nationality. State when the model performs poorly. List the main scenario limitations beside the result, especially origin-versus-nationality mapping and possible displacement from existing routes.

## 5. Data and model contract

The prepared modelling grain is **month × hotel guest nationality**. The air preparation grain is **month × flight departure origin**. A documented allocation step connects them and includes an unknown/other bucket. An allocation inferred only from aggregate totals must be labelled as uncertain.

Historical flight counts come from `data/flight_data.xlsx`. Hotel labels come from the supplied international training workbook. Its daily `New Arrivals` sum to monthly hotel check-ins. Its daily `Guests` sum to a guest-day measure. The first release must verify how same-day guests are counted before treating that sum as observed overnight guest nights. Estimated guest nights may be shown using an explicit length-of-stay assumption, but should not be presented as a directly observed label without that verification.

Use a transparent calculation for the five-stage flow. Fit a simple seasonal or regression benchmark. Try XGBoost for market and seasonal conversion effects, and use it in the product only if time-ordered back-testing shows an improvement without implausible scenario behaviour. The official international test workbook hides `Guests`, so offline metrics must come from held-out months within the training period.

Domestic hotel data may support a separate context forecast or a future total-hotel view. It is outside the first release’s flight-to-international-hotel conversion model.

## 6. Functional requirements

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| P1 | Change route capacity and load factor. | A changed input updates the full chain and hotel outputs. |
| P2 | Add or discontinue a route. | Zero or new route capacity is handled; unseen routes display wider uncertainty. |
| P3 | Expose conversion assumptions. | The user can inspect and change each stage’s assumption and see its source. |
| P4 | Compare baseline and scenario. | Both values and their difference appear by month and nationality. |
| P5 | Show uncertainty. | Results include a labelled range and identify which assumptions contribute to it. |
| P6 | Show leading drivers. | A sensitivity view states each tested lever and its range. |
| P7 | Show measured accuracy. | Historical back-test dates, WMAPE, bias, and benchmark are visible. |
| P8 | Keep country meanings clear. | Departure origin and hotel nationality have distinct labels and an inspectable mapping. |
| P9 | Reproduce the demo. | A reviewer can start the app and run the saved example with documented commands. |
| P10 | Train and evaluate from a terminal. | Separate CLI stages run from a fresh setup and write versioned metrics and models. |
| P11 | Call the model from a terminal. | A documented HTTP request returns a validated scenario response with model provenance. |
| P12 | Configure and containerize the project. | Validated YAML controls settings; a fresh Docker build starts API and web services. |

## 7. Non-functional requirements

- Scenario changes should update promptly for the aggregated data; target an interactive response rather than a long retraining operation.
- Training and data preparation run offline through separate CLI stages. The app loads prepared data and a fitted model; it does not retrain on each click.
- A fresh Docker build starts the API and web app. Terminal training and terminal HTTP prediction calls are documented and work within that setup.
- YAML configuration holds data paths, split dates, model settings, assumption locations, output paths, and service ports. It is validated on load.
- Each run writes an immutable model bundle, predictions, metrics, resolved configuration, and provenance under a unique output folder.
- All data stays aggregated. Raw competition data must not be bundled into a public demo unless its license allows it.
- Record the data version, model version, assumptions, and scenario inputs with each exported result.
- Make results readable on a laptop screen and use plain labels rather than model terminology in the main workflow.

## 8. Suggested implementation pieces

1. Data audit and preparation pipeline.
2. Origin-to-nationality allocation and assumption registry.
3. Historical benchmark and candidate XGBoost training/back-test pipeline.
4. Deterministic scenario calculation with uncertainty and sensitivity analysis.
5. Streamlit interface with interactive charts and a scenario export.
6. FastAPI endpoint, validated YAML configuration, terminal commands, Docker packaging, and versioned run artifacts as specified in [ARCHITECTURE.md](ARCHITECTURE.md).

## 9. Demo and submission presentation

Use one continuous demo story: start with a baseline month, add two weekly flights, show the change in hotel check-ins and guest nights, open the calculation chain, inspect the nationality and seasonal effects, then show the held-out accuracy. End with one planning recommendation and its uncertainty.

The 10-page PDF should follow the content outline in [SUBMISSION.md](SUBMISSION.md). The 1–2 minute video should show the same working example and agree with the app’s numbers.

## 10. Release gate

The prototype is ready to present when its data totals reconcile; changing a flight input changes hotel estimates in the expected direction; nationality and departure origin are never confused; at least one held-out back-test and simple benchmark are reported; the example scenario can be reproduced; and limitations are visible at the point of decision.
