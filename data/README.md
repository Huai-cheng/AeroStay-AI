# Local competition data

Place the five challenge workbooks in this directory before running the
pipeline. Filenames are case- and space-sensitive in the current loader:

- `flight_data.xlsx`
- `data international_train.xlsx`
- `data international_test.xlsx`
- `data domestic_train.xlsx`
- `data domestic_test.xlsx`

`Data_Dictionary.pdf` is recommended for audit/reference but is not read by the
runtime.

## Required workbook layout

Each workbook must have `Export` as its first worksheet (the supplied files
already do). Extra columns are allowed, but the following columns must retain
their exact meanings; surrounding whitespace in headers is normalized.

| Workbook | Required columns |
| --- | --- |
| `data domestic_train.xlsx` | `Date`, `Guests`, `New Arrivals`, `Same-Day Guests` |
| `data domestic_test.xlsx` | `Date`, `New Arrivals`, `Same-Day Guests` |
| `data international_train.xlsx` | `Date`, `Guests`, `New Arrivals`, `Same-Day Guests`, `Nationality` |
| `data international_test.xlsx` | `Date`, `New Arrivals`, `Same-Day Guests`, `Nationality` |
| `flight_data.xlsx` | `Date`, `Departure Country Name`, `Departure City`, `Arrival City`, `Airline Name`, `Destination`, `Average Weekly Frequency`, `Load Factor`, `Total P2P`, `Total PAX`, `Total Seats`, `Total Transfer`, `Total Transit` |

## Value expectations

- `Date` values must be parseable calendar dates.
- Training `Guests` must be numeric and non-negative.
- Arrival, seat, passenger, transfer, and transit fields should be numeric;
  blanks are preserved as missing rather than silently converted to zero.
- International `Nationality` and flight `Departure Country Name` must contain
  usable country labels. They are normalized to uppercase but are not assumed
  to be the same concept.
- Training data must include history before the evaluation/forecast period so
  previous-year features can be constructed.

The official test files intentionally omit `Guests`. They are used to produce
forecasts, not to calculate the reported offline WMAPE.

## Generated outputs

Running `python -m prototype.train_models` creates:

```text
artifacts/etl/                 model-ready derived tables
artifacts/selected_model/      fitted model, metadata, metrics and forecasts
```

Both locations are generated and ignored by Git.

The supplied datasets are for competition use only. This repository intentionally excludes the raw files and all generated data. Do not upload them to GitHub unless the data owner explicitly permits it.
