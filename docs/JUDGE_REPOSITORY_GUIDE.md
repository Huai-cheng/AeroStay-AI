# Judge-facing repository policy

## Commit

- the selected pipeline, ETL, API, both dashboard clients, and tests;
- dependency manifests, Docker files, and non-secret configuration;
- requirements, architecture, data audit, feature definitions, and limitations;
- archived experiment source and **aggregated** validation/test metrics;
- UI assets and the Streamlit theme.

## Do not commit

- licensed competition workbooks or extracts containing row-level records;
- fitted model binaries or row-level prediction files derived from those data;
- virtual environments, dependency folders, caches, builds, logs, or temporary
  files;
- secrets, local environment files, or machine-specific settings.

## Claims we can make

- Poisson XGBoost was selected by chronological rolling validation.
- On the untouched internal comparison period, it achieved 12.99% combined
  WMAPE and led the required one-model comparison set.
- Domestic and international breakdowns, bias, MAE, RMSE, and market-level
  metrics are reported in the archived aggregated result tables.
- Feature additions were tested and rejected when they did not provide a stable
  validation improvement.

## Claims we must not make

- The 12.99% figure is not an official leaderboard score: the supplied official
  test workbooks do not contain the `Guests` label.
- The scenario response is a planning simulation, not proof that a flight change
  causally creates the predicted hotel demand.
- Departure country is not automatically equivalent to hotel nationality.
- Visitor share, hotel-capture rate, and origin-to-nationality allocation are
  explicit assumptions where authoritative observations are unavailable.
