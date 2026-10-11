# Feature roles, hypotheses, and verified decisions

This is the decision record for the pooled Poisson XGBoost feature search. The
full numeric evidence is in `artifacts/pooled_poisson_feature_search/`.

## Decision rules

- **Model feature**: available with the same meaning during training and future
  prediction, and supported by chronological validation/test evidence.
- **Scenario input**: a planner can intentionally change it. The ETL converts
  it into the model's required representation.
- **ETL-derived**: computed automatically from raw data or scenario controls;
  users should not edit it directly.
- **ETL validation/filter**: protects grain, missingness, identity, time, or
  entity semantics; it is not predictive input.
- **Reporting only**: useful for interpretation or warnings but not selected as
  a model input.

## Final pooled Poisson model

| Feature | Primary role | Hypothesis | Dataset evidence | Decision |
| --- | --- | --- | --- | --- |
| Linear time trend in days | Model; ETL-derived | Demand level can drift over years | 100% coverage; 1,308 daily positions | Keep |
| Annual seasonal sine and cosine | Model; ETL-derived | Adjacent year-end dates should have adjacent seasonal coordinates | 100% coverage; removing the pair worsened rolling WMAPE from 11.87% to 12.10% | Keep as a pair |
| Weekend indicator | Model; ETL-derived | A direct weekend split can help a shallow tree even though weekday already contains it | 100% coverage; removing it worsened rolling WMAPE to 12.05% | Keep; computationally useful redundancy |
| Month category | Model; ETL-derived | Each month can have a distinct demand regime | 100% coverage | Keep |
| Day-of-week category | Model; ETL-derived | Hotel demand differs by weekday | 100% coverage | Keep |
| Domestic/international segment | Model; ETL-derived | One pooled model needs to distinguish the two demand regimes | 100% coverage | Keep |
| Hotel nationality market | Model; ETL-derived | International markets have different levels and seasonality | 100% coverage | Keep |
| New guest arrivals | Model; upstream scenario output | Arrivals are the closest supplied demand-flow signal to guests | 99.56% coverage | Keep; strongest scenario-to-model bridge |
| Same-day guests | Model; ETL-derived | Same-day activity helps separate non-overnight flow | 41.56% overall coverage because international data is sparse | Keep only with its missing indicator and imputation |
| Same-day missing indicator | Model; ETL-derived | Missing same-day data is not the same as zero | 100% coverage | Keep |
| Previous-year total guests | Model; ETL-derived | Same season last year is a strong demand reference | 71.95% coverage from 2023 onward | Keep |
| Previous-year new arrivals | Model; ETL-derived | Prior-year flow helps interpret current arrivals | 71.55% coverage; removing it was nearly neutral but slightly worse (11.879% vs 11.868%) | Keep for now |
| Year-over-year arrival ratio | Model; ETL-derived | Explicit relative growth is easier for trees to use than reconstructing division | 71.44% coverage; removing it severely worsened rolling WMAPE to 12.79% | Keep |

The final recommendation remains **B0 current baseline**. It has 14 raw
features before one-hot expansion: ten numeric features, three established
categorical features, and the pooled segment category.

## Supplied-data additions tested

| Feature | Correct role | Verified hypothesis/evidence | Final decision |
| --- | --- | --- | --- |
| Previous-year same-day guests | Candidate model; ETL-derived | Only 28.41% coverage. Added alone to the full baseline: 11.857% rolling WMAPE, a very small validation gain | Do not add yet; gain did not form the best stable combination |
| Total scheduled seat capacity | Scenario input through flights × seats; ETL-derived model candidate | 100% coverage. Added alone: 11.874%, essentially neutral; compact scheduled pack was worse | Scenario/ETL and reporting; not final model |
| Average weekly flight frequency | Scenario input; ETL-derived model candidate | 72.32% coverage from 2023. Added alone: 11.774%; useful validation signal | Keep as scenario lever and challenger feature, not final model after failed test confirmation |
| Active route count | Scenario consequence; ETL-derived | 100% coverage. Added alone: 11.848%; breadth plus concentration improved domestic validation | Scenario/reporting; not final model |
| New-route count | Scenario consequence; ETL-derived | 100% numeric coverage, but first appearance can mean left censoring or seasonal return. Added alone: 11.928%, worse | Scenario/reporting only until route-event semantics improve |
| Discontinued-route count | Scenario consequence; ETL-derived | 100% numeric coverage, but disappearance can be seasonal/censoring. Added alone: 11.895%, worse | Scenario/reporting only |
| Departure-country count | ETL-derived/reporting | Only three distinct values in the hotel horizon; added alone: 11.878%, no material gain | Reporting only |
| Year-over-year seat change | ETL-derived candidate | 72.32% coverage. Added alone: 12.508%, materially worse | Exclude from final model; retain scenario diagnostic |
| Year-over-year frequency change | ETL-derived candidate | 44.36% coverage from 2024. Added alone: 11.840%; modest validation gain | Reporting/challenger only; too sparse for final inclusion |
| Global departure-country seat concentration | ETL-derived candidate | 100% coverage. Added alone: 11.853%; frequency plus concentration won validation at 11.703% | Retain as challenger/reporting, not final model because test WMAPE worsened |
| Passenger load factor | Scenario input; conditional model candidate | 100% historically observed. Added alone: 11.938%, worse; actual future value is not known | Scenario chain only unless a genuine forecast is supplied |
| Point-to-point passenger share | Scenario-derived from transfer/transit; conditional candidate | 100% observed. Added alone: 12.001%, worse | Scenario chain only |
| Transfer passenger share | Scenario input | Exactly complements point-to-point with transit; feeding all shares is redundant | Scenario control, not model feature |
| Transit passenger share | Scenario input | Only four distinct monthly values and part of the share identity | Scenario control, not model feature |
| Seats per active route | ETL-derived diagnostic | More than 0.96 Spearman correlation with other capacity intensity measures; model was worse | Exclude |
| Seats per departure country | ETL-derived diagnostic | 0.9995 Spearman correlation with total seats; model was worse | Exclude |
| Scheduled passenger proxy (seats × load factor) | Conditional ETL-derived | Good validation challenger (11.832%) but test WMAPE was 13.31% | Scenario/reporting only |
| Destination-capacity proxy (seats × load factor × point-to-point share) | Conditional ETL-derived | Did not beat the stronger validation candidates | Scenario conversion chain, not final model |

## Entity-level aviation features

Departure-country seats, frequency, route counts, shares, passenger shares and
growth rates remain in the ETL origin table. They are **not** fed directly to a
hotel-nationality row because departure origin is not guest nationality. Their
roles are:

1. route/origin selection in the scenario UI;
2. aviation reporting;
3. scenario calculation before an explicit origin-to-nationality allocation;
4. future model candidates only after an authoritative mapping or learned
   allocation bridge is available.

The origin-match availability flag is an ETL warning, not evidence that an
exact name match is semantically correct.

## Scenario-only assumptions

These do not come from the supplied hotel/flight training data and must remain
visible adjustable assumptions:

- visitor share of destination passengers;
- hotel-capture rate;
- origin-to-nationality allocation share;
- average length of stay, if later used for a true nights calculation.

They must not be silently learned, imputed as facts, or presented as causal
effects.

## ETL validation and filters

- Preserve source grain: 2022 flight data is monthly; 2023 onward is daily.
- Aggregate counts by summation and recompute ratios from aggregated counts.
- Preserve missing weekly frequency in 2022. Never translate missing frequency
  into zero flights.
- Enforce passengers = point-to-point + transfer + transit when components are
  complete.
- Use time-blocked splits and compute lags only from prior dates.
- Preserve missing same-day values and add a missing indicator; never zero-pad.
- Prevent exact departure-country-to-nationality joins from being treated as a
  verified behavioral mapping.
- Reject or warn on scenario values outside historical ranges.

## Final evidence

- 67 feature definitions × 2 rolling folds = 134 chronological validation fits.
- Current baseline rolling WMAPE: **11.868%**.
- Validation winner (baseline + frequency + concentration): **11.703%**.
- Current baseline held-out WMAPE: **12.987%**.
- Validation winner held-out WMAPE: **13.102%**.
- Challenger minus baseline: **+0.115 percentage points**; paired month-cluster
  bootstrap 95% interval: **+0.019 to +0.221 points**.
- Therefore no tested new feature combination has enough out-of-time evidence
  to replace the current pooled Poisson feature definition.
