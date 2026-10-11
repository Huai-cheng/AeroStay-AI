# Official Requirements and Delivered Data Audit

Checked: 2026-10-10

## Authoritative challenge requirements

The official DCT challenge asks for an interactive simulator connecting aviation changes to hotel demand. The user must be able to alter aviation or market factors and see hotel guest numbers by source market and season.

The required conversion chain is:

```text
scheduled seats
  → arriving passengers through load factor
  → inbound visitors after transfer/transit and purpose adjustment
  → hotel guest nights through hotel capture and length of stay
```

The official statement explicitly encourages two layers:

1. A transparent parametric layer.
2. A machine-learning layer such as gradient boosting or regression.

Therefore, selecting Demand XGBoost as the only machine-learning approach does not mean building an XGBoost-only product. The parametric scenario layer remains required.

Source: https://challengeon.atrc.ae/en/challenges/atp2026/pages/dct-challenge-statement?lang=en

## Delivered hotel data

### Domestic train

- 1,308 daily rows from 2022-01-01 through 2025-07-31.
- One row per date.
- Columns: Date, Guests, New Arrivals, Same-Day Guests, Residence group.
- No missing values.

### Domestic test

- 212 daily rows from 2025-08-01 through 2026-02-28.
- `Guests` is hidden.
- New Arrivals and Same-Day Guests are provided.

### International train

- 58,622 nationality-date rows over 1,308 dates.
- 45 nationalities overall, with 40–45 rows per date.
- `New Arrivals` is missing for 0.45% of rows.
- `Same-Day Guests` is missing for 59.75% of rows.

### International test

- 9,202 nationality-date rows over 212 dates.
- 39–45 nationalities per date.
- `Guests` is hidden.
- `New Arrivals` is missing for 0.02% of rows.
- `Same-Day Guests` is missing for 47.84% of rows.

## Correct target interpretation

The dictionary states:

- `Guests` is total guests recorded for the date.
- `New Arrivals` is a subset of `Guests`, distinguished from continuing stays.
- `Same-Day Guests` visited and departed without an overnight stay.

This supports the following implementation:

```text
competition model target = Guests
daily overnight guest nights = predicted Guests - scenario Same-Day Guests
```

For international rows, missing same-day values can mean zero, suppressed, unavailable, or not applicable. The product must expose that ambiguity. A missing indicator and sensitivity range are safer than silently treating every missing value as known zero.

## Delivered flight data

- 117,608 rows and 26 columns.
- Date range: 2022-01-01 through 2026-02-28.
- 33 departure countries, multiple cities and airlines.
- 2022 contains 12 unique monthly dates.
- 2023 and 2024 contain every daily date; 2025 contains every daily date; 2026 contains 59 dates through February.
- The workbook therefore changes from monthly grain in 2022 to daily grain from 2023 onward.

Core identities are exact in the delivered workbook:

```text
Total PAX = Total P2P + Total Transfer + Total Transit
Load Factor = Total PAX / Total Seats
```

Load factor exceeds 100% in 9,896 rows, consistent with the dictionary's caveat about overbooking or infant-count differences.

Average Weekly Frequency and class-level fields are missing in approximately 1.03% of rows, concentrated in 2022; they are populated from 2023 onward. This contradicts the dictionary statement that frequency is missing in most observed rows.

## Fields described online but absent locally

The public page says teams may receive richer hotel and supporting reference data. The local directory does not contain:

- Hotel occupancy.
- Hotel room supply.
- Average length of stay.
- Visitor or purpose-of-travel share.
- Hotel-capture rate.
- Aircraft type.
- Event calendars.
- Source-market public holidays.
- A separate base-seasonality profile.

The simulator may still expose relevant levers, but absent quantities must be labelled as assumptions, not trained observations.

## Revised product architecture

### Parametric scenario layer

```text
seats = frequency × seats per flight
passengers = seats × load factor
destination passengers = passengers - transfer - transit
visitors = destination passengers × visitor share assumption
hotel guests = visitors × hotel-capture assumption
```

### Machine-learning layer

Use one named ML approach: Demand XGBoost. It models the supplied `Guests` target using known or scenario-reconstructed demand features, market, season, and history.

### Guest-night output

```text
guest nights = predicted Guests - Same-Day Guests
```

If the team instead uses average length of stay in the chain, it must explain how that assumption reconciles to the supplied daily stock target and avoid counting length of stay twice.

## Submission and governance requirements

- Deadline: 11 October 2026, 23:59 GMT+4.
- Ten-slide PDF proposal deck.
- One-to-two-minute prototype video.
- English submission.
- Team of 3–4 with the published eligibility requirements.
- Declare AI use and be able to explain the work.
- Do not publicly share competition data or unapproved challenge materials.

Sources:

- https://challengeon.atrc.ae/en/challenges/atp2026/pages/timeline?lang=en
- https://challengeon.atrc.ae/en/challenges/atp2026/pages/faq?lang=en
- https://challengeon.atrc.ae/en/challenges/atp2026/agreements?lang=en
