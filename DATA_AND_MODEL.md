# Data and modelling specification

This is a working design. The data dictionary and workbook headers, dates, and selected relationships have received an initial check. Detailed data quality and target-definition checks remain open.

## Available files and intended roles

| File | Intended role to verify |
| --- | --- |
| `data/flight_data.xlsx` | Flight operations, routes, seats, realised passenger counts, and transfer/transit counts; 2022 rows are monthly and 2023 onward rows are daily. |
| `data/data international_train.xlsx` / `data/data international_test.xlsx` | Daily hotel records by nationality, January 2022–July 2025 train and August 2025–February 2026 test; `Guests` is absent from test. |
| `data/data domestic_train.xlsx` / `data/data domestic_test.xlsx` | Daily domestic hotel records at citywide date grain; useful for a separate total-demand view, not the direct international flight conversion. |
| `data/Data_Dictionary.pdf` | Authoritative field definitions, units, caveats, and permitted joins. |

The brief also promises hotel guest nights, average length of stay, occupancy, seasonality, events, and holidays. These have not been found as direct fields or separate reference tables in the current pack. The flight file does include realised passenger counts. Confirm missing elements before claiming a complete observed conversion chain.

## First data audit

For each sheet/table, record its grain, date range, key columns, country codes, units, missing values, duplicates, and any pre-existing train/test split. Then check:

1. Whether seats are per flight, per week, or per period; whether counts are arrivals only or both directions.
2. Whether passenger traffic excludes or includes transfers and transit passengers.
3. Whether hotel guest arrivals, guest nights, occupancy, and average length of stay are available at matching month and market grain.
4. Whether the historical months in the flight and hotel files overlap.
5. Whether hotel nationality has an `unknown`/`other` category and whether totals reconcile.
6. Whether supplied test periods follow train periods in time. Preserve the supplied test set as final evaluation data unless its meaning requires clarification.

## Grain and country reconciliation

Use a canonical **month × flight departure origin** table for air supply and realised passengers. Keep a distinct **month × guest nationality** table for hotel outcomes. Never relabel departure origin as nationality.

If the pack contains a defensible crosswalk, estimate a time-aware matrix `P(nationality | departure origin, month/season)`. If it does not, treat the matrix as an assumption: use documented expert input, external aggregate evidence permitted by the competition, or a constrained pooled estimate. Expose its uncertainty. A one-to-one country join should be used only when evidence supports it, and its bias should be acknowledged.

The mapping must conserve totals: allocated travellers from an origin cannot exceed the travellers entering the allocation, and nationality shares for each origin/period must sum to one. Provide an `unknown/other` bucket rather than silently dropping unmatched passengers.

## Transparent conversion layer

At a consistent period and route/market grain:

```text
arriving_passengers = scheduled_arrival_seats × load_factor
inbound_visitors    = arriving_passengers × (1 − transfer_transit_share) × nonresident_visitor_share
hotel_guests        = inbound_visitors × hotel_capture_rate
guest_nights        = hotel_guests × average_length_of_stay
```

The exact definition of each rate must match the available data. If `nonresident_visitor_share` already excludes transfers, avoid applying the transfer adjustment twice. Allocate origin-based visitors to hotel nationality markets using the documented crosswalk at the appropriate stage. Estimate rates by market and season where reliable; pool sparse markets. Bound shares between 0 and 1 and length of stay above 0. Display parameter provenance and editable scenario overrides.

## Statistical layer

Start with a simple historical/seasonal benchmark and the parametric model. Add a regression or gradient-boosted correction only if it improves forward-period validation. Candidate features include month, market, capacity, frequency, observed or estimated load factor, events, holidays, and lagged demand. Use only features that would be known when a planner runs a future scenario. Keep the model response to user controls inspectable; a correction must not erase the physical logic of the conversion chain.

For a new route or country with little history, use pooled estimates and show that its uncertainty is higher. No model should infer a precise nationality mix from departure country alone without evidence.

## Back-testing and uncertainty

- Use time-ordered training/validation. Treat the supplied test workbooks according to their documented role; do not tune on the final test period.
- Compare with a seasonal-naive benchmark and the transparent parametric layer. Evaluate guest arrivals and guest nights separately at relevant month/market and total levels.
- Report `WMAPE = sum(abs(actual − predicted)) / sum(abs(actual)) × 100%` over the stated test set. Define treatment of zero or missing actuals, and include bias so underprediction and overprediction are visible.
- Check stage-level errors where passenger and visitor observations exist; a good hotel total can conceal errors that cancel.
- Build scenario ranges from historical residuals and plausible parameter/crosswalk ranges. Label these as empirical intervals or assumption ranges as appropriate; do not call them calibrated confidence intervals without coverage testing.
- Rank factor effects by changing each lever over a stated, plausible range. If global sensitivity analysis is used, specify the joint input ranges and dependencies.

## Known limitations to revisit after audit

- Departure country is an imperfect proxy for guest nationality, especially for connecting itineraries.
- Aggregated data may not identify visitor purpose, residents, hotel capture, or length of stay at route level.
- Schedule changes may displace travellers from other routes rather than create wholly new demand.
- Hotel demand also depends on prices, events, visa policy, and capacity; correlation alone does not establish the causal effect of a route.
- New-route predictions and out-of-range changes require broader uncertainty than interpolation within observed routes.

Maintain a dated assumption register in this file or a later machine-readable configuration once the actual data is inspected.
