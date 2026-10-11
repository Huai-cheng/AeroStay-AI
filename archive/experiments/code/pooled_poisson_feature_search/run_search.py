"""Rolling-validation feature search for the pooled Poisson XGBoost model."""

from __future__ import annotations

import itertools
import json
import math
import sys
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipelines" / "feature_group_xgboost"))
import run_experiments as shared  # noqa: E402


OUTPUT = ROOT / "artifacts" / "pooled_poisson_feature_search"
EPS = 1e-9
RANDOM_STATE = 20261010
DATA_VERSION = "frequency_missing_preserved_v2"

ROLLING_FOLDS = (
    ("fold_1", pd.Timestamp("2023-07-31"), pd.Timestamp("2023-08-01"), pd.Timestamp("2024-01-31")),
    ("fold_2", pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-01"), pd.Timestamp("2024-07-31")),
)
TEST_START = pd.Timestamp("2024-08-01")
TEST_END = pd.Timestamp("2025-02-28")

MARKET_CATEGORICAL = ["market", "segment"]
CALENDAR_CATEGORICAL = ["month_category", "day_of_week_category"]

CORE_NUMERIC = [
    "linear_time_trend_days",
    "new_arrivals",
    "same_day_guests",
    "same_day_guests_missing_indicator",
    "previous_year_total_guests",
]
CURRENT_BASE_NUMERIC = shared.BASE_NUMERIC.copy()
CURRENT_BASE_CATEGORICAL = shared.BASE_CATEGORICAL + ["segment"]

HISTORICAL = {
    "prior_arrivals": "previous_year_new_arrivals",
    "arrival_ratio": "year_over_year_arrival_ratio",
    "prior_same_day": "previous_year_same_day_guests",
}
SCHEDULED = OrderedDict(
    [
        ("total_seats", "global_total_scheduled_seats"),
        ("weekly_frequency", "global_average_weekly_flight_frequency"),
        ("active_routes", "global_active_route_count"),
        ("new_routes", "global_new_route_count"),
        ("discontinued_routes", "global_discontinued_route_count"),
        ("departure_countries", "global_departure_country_count"),
        ("yoy_seats", "global_year_over_year_seat_change"),
        ("yoy_frequency", "global_year_over_year_frequency_change"),
        ("seat_concentration", "global_origin_market_seat_concentration"),
    ]
)
PASSENGER = OrderedDict(
    [
        ("load_factor", "global_passenger_load_factor"),
        ("point_to_point_share", "global_point_to_point_passenger_share"),
        ("transfer_share", "global_transfer_passenger_share"),
        ("transit_share", "global_transit_passenger_share"),
    ]
)
DERIVED = OrderedDict(
    [
        ("seats_per_active_route", "derived_seats_per_active_route"),
        ("seats_per_departure_country", "derived_seats_per_departure_country"),
        ("scheduled_passenger_proxy", "derived_scheduled_passenger_proxy"),
        ("destination_capacity_proxy", "derived_destination_capacity_proxy"),
    ]
)


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["derived_seats_per_active_route"] = (
        frame["global_total_scheduled_seats"]
        / frame["global_active_route_count"].replace(0, np.nan)
    )
    frame["derived_seats_per_departure_country"] = (
        frame["global_total_scheduled_seats"]
        / frame["global_departure_country_count"].replace(0, np.nan)
    )
    frame["derived_scheduled_passenger_proxy"] = (
        frame["global_total_scheduled_seats"] * frame["global_passenger_load_factor"]
    )
    frame["derived_destination_capacity_proxy"] = (
        frame["derived_scheduled_passenger_proxy"]
        * frame["global_point_to_point_passenger_share"]
    )
    return frame


def wmape(actual: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.abs(actual - prediction).sum() / max(np.abs(actual).sum(), EPS))


def score(frame: pd.DataFrame, prediction: np.ndarray) -> dict[str, float]:
    actual = frame["guests"].to_numpy(float)
    prediction = np.clip(np.asarray(prediction, dtype=float), 0.0, None)
    error = prediction - actual
    scored = frame[["market", "segment", "guests"]].copy()
    scored["prediction"] = prediction
    market_wmapes = [
        wmape(part["guests"].to_numpy(float), part["prediction"].to_numpy(float))
        for _, part in scored.groupby("market", observed=True)
    ]
    result = {
        "rows": int(len(frame)),
        "wmape": wmape(actual, prediction),
        "bias_pct": float(error.sum() / max(actual.sum(), EPS)),
        "mae": float(mean_absolute_error(actual, prediction)),
        "rmse": float(math.sqrt(mean_squared_error(actual, prediction))),
        "r2": float(r2_score(actual, prediction)),
        "macro_market_wmape": float(np.mean(market_wmapes)),
        "p90_market_wmape": float(np.quantile(market_wmapes, 0.90)),
    }
    for segment, part in scored.groupby("segment", observed=True):
        key = str(segment).lower()
        result[f"{key}_wmape"] = wmape(
            part["guests"].to_numpy(float), part["prediction"].to_numpy(float)
        )
        result[f"{key}_bias_pct"] = float(
            (part["prediction"] - part["guests"]).sum()
            / max(part["guests"].sum(), EPS)
        )
    return result


def transformer(numeric: list[str], categorical: list[str], scale: bool = False) -> ColumnTransformer:
    numeric_steps: list[tuple] = [
        ("impute", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True))
    ]
    if scale:
        numeric_steps.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), numeric),
            (
                "category",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            ),
        ]
    )


def xgb_params(early_stopping: bool = True) -> dict:
    values = {
        "n_estimators": 1600,
        "learning_rate": 0.03,
        "max_depth": 5,
        "min_child_weight": 15,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 10.0,
        "reg_alpha": 0.1,
        "tree_method": "hist",
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }
    if early_stopping:
        values["early_stopping_rounds"] = 75
    return values


def fit_validation(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    objective: str = "poisson",
) -> tuple[np.ndarray, int]:
    features = numeric + categorical
    prep = transformer(numeric, categorical)
    x_train = prep.fit_transform(train[features])
    x_validation = prep.transform(validation[features])
    y_train = train["guests"].to_numpy(float)
    y_validation = validation["guests"].to_numpy(float)
    model_objective = "count:poisson" if objective == "poisson" else "reg:squarederror"
    y_train_fit = np.log1p(y_train) if objective == "log_target" else y_train
    y_validation_fit = np.log1p(y_validation) if objective == "log_target" else y_validation
    model = XGBRegressor(
        objective=model_objective,
        eval_metric="rmse" if objective == "log_target" else "mae",
        **xgb_params(early_stopping=True),
    )
    model.fit(x_train, y_train_fit, eval_set=[(x_validation, y_validation_fit)], verbose=False)
    prediction = model.predict(x_validation)
    if objective == "log_target":
        prediction = np.expm1(prediction)
    return np.clip(prediction, 0.0, None), int(model.best_iteration) + 1


def fit_final_xgb(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    trees: int,
    objective: str = "poisson",
) -> np.ndarray:
    features = numeric + categorical
    prep = transformer(numeric, categorical)
    x_train = prep.fit_transform(train[features])
    x_test = prep.transform(test[features])
    target = train["guests"].to_numpy(float)
    model = XGBRegressor(
        objective="count:poisson" if objective == "poisson" else "reg:squarederror",
        n_estimators=max(1, trees),
        learning_rate=0.03,
        max_depth=5,
        min_child_weight=15,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=10.0,
        reg_alpha=0.1,
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    fit_target = np.log1p(target) if objective == "log_target" else target
    model.fit(x_train, fit_target, verbose=False)
    prediction = model.predict(x_test)
    if objective == "log_target":
        prediction = np.expm1(prediction)
    return np.clip(prediction, 0.0, None)


def fit_final_linear(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
) -> np.ndarray:
    features = numeric + categorical
    prep = transformer(numeric, categorical, scale=True)
    model = Pipeline([("preprocess", prep), ("model", Ridge(alpha=10.0))])
    model.fit(train[features], train["guests"].to_numpy(float))
    return np.clip(model.predict(test[features]), 0.0, None)


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def definitions() -> OrderedDict[str, tuple[list[str], list[str], str]]:
    core_cat = MARKET_CATEGORICAL + CALENDAR_CATEGORICAL
    experiments: OrderedDict[str, tuple[list[str], list[str], str]] = OrderedDict()

    def add(name: str, numeric: list[str], categorical: list[str] | None, hypothesis: str) -> None:
        experiments[name] = (unique(numeric), unique(categorical or core_cat), hypothesis)

    add("B0_current_baseline", CURRENT_BASE_NUMERIC, CURRENT_BASE_CATEGORICAL,
        "Reproduce the established pooled baseline, including known redundancies.")
    add("L0_lean_core", CORE_NUMERIC, core_cat,
        "Use one compact feature for trend, calendar, current flow, prior demand, market and segment.")
    add("C1_lean_plus_cyclic_season", CORE_NUMERIC + ["annual_seasonal_sine", "annual_seasonal_cosine"], core_cat,
        "Smooth annual position may complement categorical month boundaries.")
    add("C2_lean_plus_weekend", CORE_NUMERIC + ["weekend_indicator"], core_cat,
        "Weekend may provide an easier tree split despite being determined by day of week.")
    add("C3_cyclic_without_month", CORE_NUMERIC + ["annual_seasonal_sine", "annual_seasonal_cosine"], MARKET_CATEGORICAL + ["day_of_week_category"],
        "A smooth cyclic calendar may generalize better than month categories.")

    add("H1_prior_arrivals", CORE_NUMERIC + [HISTORICAL["prior_arrivals"]], core_cat,
        "Prior-year arrivals add seasonal flow history.")
    add("H2_arrival_ratio", CORE_NUMERIC + [HISTORICAL["arrival_ratio"]], core_cat,
        "The year-over-year ratio exposes an interaction between current and prior arrivals.")
    add("H3_prior_same_day", CORE_NUMERIC + [HISTORICAL["prior_same_day"]], core_cat,
        "Prior-year same-day volume helps separate overnight from non-overnight behavior.")
    add("H4_prior_arrivals_plus_same_day", CORE_NUMERIC + [HISTORICAL["prior_arrivals"], HISTORICAL["prior_same_day"]], core_cat,
        "Combine prior arrival scale with prior same-day behavior.")
    add("H5_ratio_plus_same_day", CORE_NUMERIC + [HISTORICAL["arrival_ratio"], HISTORICAL["prior_same_day"]], core_cat,
        "Combine relative arrival growth with prior same-day behavior.")
    add("H6_all_historical", CORE_NUMERIC + list(HISTORICAL.values()), core_cat,
        "Test whether XGBoost benefits from all correlated historical representations.")

    # Ablate and extend the stronger established baseline. These experiments
    # answer whether a new feature adds information after the current model's
    # useful redundancies and interactions have already been supplied.
    add("A0_baseline_without_weekend", [f for f in CURRENT_BASE_NUMERIC if f != "weekend_indicator"], CURRENT_BASE_CATEGORICAL,
        "Verify whether the weekend shortcut helps after day of week is encoded.")
    add("A1_baseline_without_cyclic", [f for f in CURRENT_BASE_NUMERIC if f not in {"annual_seasonal_sine", "annual_seasonal_cosine"}], CURRENT_BASE_CATEGORICAL,
        "Verify whether month category is sufficient without cyclic annual coordinates.")
    add("A2_baseline_without_prior_arrivals", [f for f in CURRENT_BASE_NUMERIC if f != HISTORICAL["prior_arrivals"]], CURRENT_BASE_CATEGORICAL,
        "Measure whether prior arrivals add value once the arrival ratio is present.")
    add("A3_baseline_without_arrival_ratio", [f for f in CURRENT_BASE_NUMERIC if f != HISTORICAL["arrival_ratio"]], CURRENT_BASE_CATEGORICAL,
        "Measure whether the derived arrival ratio helps beyond current and prior arrivals.")
    add("A4_baseline_plus_prior_same_day", CURRENT_BASE_NUMERIC + [HISTORICAL["prior_same_day"]], CURRENT_BASE_CATEGORICAL,
        "Test the previously promising prior-year same-day feature on the full established baseline.")

    for short_name, feature in SCHEDULED.items():
        add(f"A5_baseline_plus_{short_name}", CURRENT_BASE_NUMERIC + [feature], CURRENT_BASE_CATEGORICAL,
            f"Measure the unique value of {short_name.replace('_', ' ')} after the established demand baseline.")
    add("A6_baseline_plus_seat_level_growth", CURRENT_BASE_NUMERIC + [SCHEDULED["total_seats"], SCHEDULED["yoy_seats"]], CURRENT_BASE_CATEGORICAL,
        "Add capacity level and growth to the established baseline.")
    add("A7_baseline_plus_breadth_mix", CURRENT_BASE_NUMERIC + [SCHEDULED["active_routes"], SCHEDULED["seat_concentration"]], CURRENT_BASE_CATEGORICAL,
        "Add network breadth and origin concentration to the established baseline.")
    add("A8_baseline_plus_compact_scheduled", CURRENT_BASE_NUMERIC + [SCHEDULED[k] for k in ("total_seats", "yoy_seats", "active_routes", "seat_concentration")], CURRENT_BASE_CATEGORICAL,
        "Add one scheduled feature for scale, growth, breadth and mix to the established baseline.")
    add("A9_baseline_plus_prior_same_day_compact", CURRENT_BASE_NUMERIC + [HISTORICAL["prior_same_day"]] + [SCHEDULED[k] for k in ("total_seats", "yoy_seats", "active_routes", "seat_concentration")], CURRENT_BASE_CATEGORICAL,
        "Combine the historical extension with the compact scheduled feature set.")

    add("Q1_baseline_plus_load_factor", CURRENT_BASE_NUMERIC + [PASSENGER["load_factor"]], CURRENT_BASE_CATEGORICAL,
        "Test conditional planned load factor after the established baseline.")
    add("Q2_baseline_plus_point_to_point", CURRENT_BASE_NUMERIC + [PASSENGER["point_to_point_share"]], CURRENT_BASE_CATEGORICAL,
        "Test conditional destination-passenger share after the established baseline.")
    add("Q3_baseline_plus_load_and_point_to_point", CURRENT_BASE_NUMERIC + [PASSENGER["load_factor"], PASSENGER["point_to_point_share"]], CURRENT_BASE_CATEGORICAL,
        "Test the compact passenger conversion pair after the established baseline.")
    add("R1_baseline_plus_scheduled_passenger_proxy", CURRENT_BASE_NUMERIC + [DERIVED["scheduled_passenger_proxy"]], CURRENT_BASE_CATEGORICAL,
        "Test the seats-times-load-factor proxy after the established baseline.")
    add("R2_baseline_plus_destination_capacity_proxy", CURRENT_BASE_NUMERIC + [DERIVED["destination_capacity_proxy"]], CURRENT_BASE_CATEGORICAL,
        "Test the destination-capacity proxy after the established baseline.")

    historical_base = CORE_NUMERIC + [HISTORICAL["prior_same_day"]]
    for short_name, feature in SCHEDULED.items():
        add(f"S1_{short_name}", historical_base + [feature], core_cat,
            f"Isolate the incremental scheduled/network information in {short_name.replace('_', ' ')}.")

    add("S2_seat_level_growth", historical_base + [SCHEDULED["total_seats"], SCHEDULED["yoy_seats"]], core_cat,
        "Represent scheduled capacity level and growth without frequency duplication.")
    add("S3_breadth_mix", historical_base + [SCHEDULED["active_routes"], SCHEDULED["seat_concentration"]], core_cat,
        "Represent network breadth and concentration rather than only scale.")
    add("S4_compact_scheduled", historical_base + [SCHEDULED[k] for k in ("total_seats", "yoy_seats", "active_routes", "seat_concentration")], core_cat,
        "Use one scheduled feature each for scale, growth, breadth and mix.")
    add("S5_scale_frequency", historical_base + [SCHEDULED["total_seats"], SCHEDULED["weekly_frequency"]], core_cat,
        "Test whether frequency adds accessibility beyond total capacity.")
    add("S6_route_dynamics", historical_base + [SCHEDULED["new_routes"], SCHEDULED["discontinued_routes"]], core_cat,
        "Test explicit network openings and closures together.")
    add("S7_all_schedule_safe", historical_base + list(SCHEDULED.values()), core_cat,
        "Diagnostic safe stress test using every schedule-derived global feature.")

    add("P1_load_factor", historical_base + [PASSENGER["load_factor"]], core_cat,
        "Observed or planned utilization may convert seats into passengers.")
    add("P2_point_to_point", historical_base + [PASSENGER["point_to_point_share"]], core_cat,
        "Destination passenger share is closer to hotel demand than total movements.")
    add("P3_load_plus_point_to_point", historical_base + [PASSENGER["load_factor"], PASSENGER["point_to_point_share"]], core_cat,
        "Compact passenger conversion uses utilization and destination share.")
    add("P4_transfer_plus_transit", historical_base + [PASSENGER["transfer_share"], PASSENGER["transit_share"]], core_cat,
        "Two components can represent the excluded passenger share without collinearity from all three.")
    add("P5_all_passenger_redundant", historical_base + list(PASSENGER.values()), core_cat,
        "Diagnostic test of intentionally redundant passenger shares.")

    add("D1_seats_per_active_route", historical_base + [DERIVED["seats_per_active_route"]], core_cat,
        "Average route gauge/intensity may differ from total network size.")
    add("D2_seats_per_country", historical_base + [DERIVED["seats_per_departure_country"]], core_cat,
        "Capacity intensity per source country may capture market depth.")
    add("D3_scheduled_passenger_proxy", historical_base + [DERIVED["scheduled_passenger_proxy"]], core_cat,
        "Seats multiplied by load factor approximates passengers.")
    add("D4_destination_capacity_proxy", historical_base + [DERIVED["destination_capacity_proxy"]], core_cat,
        "Seats times load factor times point-to-point share approximates destination passengers.")
    add("D5_compact_plus_destination_proxy", historical_base + [SCHEDULED[k] for k in ("active_routes", "yoy_seats", "seat_concentration")] + [DERIVED["destination_capacity_proxy"]], core_cat,
        "Combine destination capacity with scheduled growth, breadth and mix.")

    # Second-stage combinations use only patterns observed in rolling
    # validation: frequency helped international rows, breadth/mix helped
    # domestic rows, and prior same-day guests helped the pooled signal.
    add("Z1_frequency_plus_prior_same_day", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], HISTORICAL["prior_same_day"]], CURRENT_BASE_CATEGORICAL,
        "Combine service intensity with prior-year same-day behavior.")
    add("Z2_frequency_plus_active_routes", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], SCHEDULED["active_routes"]], CURRENT_BASE_CATEGORICAL,
        "Combine service intensity with network breadth.")
    add("Z3_frequency_plus_concentration", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], SCHEDULED["seat_concentration"]], CURRENT_BASE_CATEGORICAL,
        "Combine service intensity with origin-market concentration.")
    add("Z4_frequency_plus_breadth_mix", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], SCHEDULED["active_routes"], SCHEDULED["seat_concentration"]], CURRENT_BASE_CATEGORICAL,
        "Combine the strongest international-facing feature with the strongest domestic-facing pair.")
    add("Z5_prior_same_day_plus_breadth_mix", CURRENT_BASE_NUMERIC + [HISTORICAL["prior_same_day"], SCHEDULED["active_routes"], SCHEDULED["seat_concentration"]], CURRENT_BASE_CATEGORICAL,
        "Combine historical same-day behavior with network breadth and mix.")
    add("Z6_frequency_prior_same_day_breadth_mix", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], HISTORICAL["prior_same_day"], SCHEDULED["active_routes"], SCHEDULED["seat_concentration"]], CURRENT_BASE_CATEGORICAL,
        "Compact union of the validation-positive historical and aviation signals.")
    add("Z7_frequency_level_and_growth", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], SCHEDULED["yoy_frequency"]], CURRENT_BASE_CATEGORICAL,
        "Represent flight frequency level and year-over-year direction together.")
    add("Z8_frequency_plus_total_seats", CURRENT_BASE_NUMERIC + [SCHEDULED["weekly_frequency"], SCHEDULED["total_seats"]], CURRENT_BASE_CATEGORICAL,
        "Test whether service frequency and capacity scale contain complementary information.")
    return experiments


def coverage_table(frame: pd.DataFrame, candidate_features: list[str]) -> pd.DataFrame:
    rows = []
    for feature in candidate_features:
        for segment, part in [("Overall", frame)] + list(frame.groupby("segment", observed=True)):
            values = part[feature]
            rows.append(
                {
                    "feature": feature,
                    "segment": segment,
                    "rows": len(part),
                    "coverage_pct": float(values.notna().mean()),
                    "distinct_non_null": int(values.nunique(dropna=True)),
                    "zero_pct_of_non_null": float(values.dropna().eq(0).mean()) if values.notna().any() else np.nan,
                    "first_available_date": str(part.loc[values.notna(), "date"].min().date()) if values.notna().any() else "",
                    "last_available_date": str(part.loc[values.notna(), "date"].max().date()) if values.notna().any() else "",
                }
            )
    return pd.DataFrame(rows)


def correlation_table(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    monthly = frame.sort_values("date").drop_duplicates("month")
    corr = monthly[features].corr(method="spearman")
    rows = []
    for left, right in itertools.combinations(features, 2):
        value = corr.loc[left, right]
        if pd.notna(value):
            rows.append({"feature_1": left, "feature_2": right, "spearman": float(value), "absolute_spearman": abs(float(value))})
    return pd.DataFrame(rows).sort_values("absolute_spearman", ascending=False)


def rolling_search(frame: pd.DataFrame, experiments: OrderedDict) -> tuple[pd.DataFrame, pd.DataFrame]:
    fold_rows: list[dict] = []
    summary_rows: list[dict] = []
    cache_path = OUTPUT / "rolling_fold_results.csv"
    cached = pd.read_csv(cache_path) if cache_path.exists() else pd.DataFrame()
    for name, (numeric, categorical, hypothesis) in experiments.items():
        started = time.perf_counter()
        numeric_text = "|".join(numeric)
        categorical_text = "|".join(categorical)
        reuse = pd.DataFrame()
        if not cached.empty:
            reuse = cached[
                cached["experiment"].eq(name)
                & cached["numeric_features"].eq(numeric_text)
                & cached["categorical_features"].eq(categorical_text)
            ].copy()
        cache_is_current = (
            "data_version" in reuse.columns
            and not reuse.empty
            and reuse["data_version"].eq(DATA_VERSION).all()
        )
        if cache_is_current and len(reuse) == len(ROLLING_FOLDS) and set(reuse["fold"]) == {fold[0] for fold in ROLLING_FOLDS}:
            experiment_folds = reuse.to_dict(orient="records")
            fold_rows.extend(experiment_folds)
        else:
            experiment_folds = []
            for fold_name, train_end, validation_start, validation_end in ROLLING_FOLDS:
                train = frame[frame["date"].le(train_end)].copy()
                validation = frame[frame["date"].between(validation_start, validation_end, inclusive="both")].copy()
                prediction, trees = fit_validation(train, validation, numeric, categorical)
                values = score(validation, prediction)
                row = {
                    "experiment": name,
                    "fold": fold_name,
                    "train_end": str(train_end.date()),
                    "validation_start": str(validation_start.date()),
                    "validation_end": str(validation_end.date()),
                    "numeric_features": numeric_text,
                    "categorical_features": categorical_text,
                    "hypothesis": hypothesis,
                    "data_version": DATA_VERSION,
                    "best_trees": trees,
                    **values,
                }
                fold_rows.append(row)
                experiment_folds.append(row)
        fold_frame = pd.DataFrame(experiment_folds)
        weights = fold_frame["rows"].to_numpy(float)
        summary = {
            "experiment": name,
            "numeric_features": "|".join(numeric),
            "categorical_features": "|".join(categorical),
            "feature_count_before_encoding": len(numeric) + len(categorical),
            "hypothesis": hypothesis,
            "rolling_wmape": float(np.average(fold_frame["wmape"], weights=weights)),
            "rolling_bias_pct": float(np.average(fold_frame["bias_pct"], weights=weights)),
            "rolling_domestic_wmape": float(np.average(fold_frame["domestic_wmape"], weights=weights)),
            "rolling_international_wmape": float(np.average(fold_frame["international_wmape"], weights=weights)),
            "rolling_macro_market_wmape": float(np.average(fold_frame["macro_market_wmape"], weights=weights)),
            "rolling_p90_market_wmape": float(np.average(fold_frame["p90_market_wmape"], weights=weights)),
            "fold_wmape_std": float(fold_frame["wmape"].std(ddof=0)),
            "median_best_trees": int(round(fold_frame["best_trees"].median())),
            "seconds": round(time.perf_counter() - started, 3),
        }
        summary_rows.append(summary)
        print(f"{name}: rolling={summary['rolling_wmape']:.4%} domestic={summary['rolling_domestic_wmape']:.4%} international={summary['rolling_international_wmape']:.4%}", flush=True)
    summary = pd.DataFrame(summary_rows).sort_values("rolling_wmape").reset_index(drop=True)
    baseline = float(summary.loc[summary["experiment"].eq("B0_current_baseline"), "rolling_wmape"].iloc[0])
    lean = float(summary.loc[summary["experiment"].eq("L0_lean_core"), "rolling_wmape"].iloc[0])
    summary["delta_vs_current_baseline"] = summary["rolling_wmape"] - baseline
    summary["delta_vs_lean"] = summary["rolling_wmape"] - lean
    return pd.DataFrame(fold_rows), summary


def evaluate_test_finalists(frame: pd.DataFrame, experiments: OrderedDict, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    # Predeclared anchors plus the best overall, best schedule-safe, and best passenger/derived diagnostic.
    anchors = ["B0_current_baseline", "L0_lean_core", "S4_compact_scheduled"]
    best_overall = str(summary.iloc[0]["experiment"])
    conditional_prefixes = ("P", "Q", "R", "D3", "D4", "D5")
    safe_names = [name for name in summary["experiment"] if not name.startswith(conditional_prefixes)]
    best_safe = str(summary[summary["experiment"].isin(safe_names)].iloc[0]["experiment"])
    conditional = summary[summary["experiment"].str.startswith(conditional_prefixes)]
    best_conditional = str(conditional.iloc[0]["experiment"])
    finalists = unique(anchors + [best_overall, best_safe, best_conditional])

    train = frame[frame["date"].lt(TEST_START)].copy()
    test = frame[frame["date"].between(TEST_START, TEST_END, inclusive="both")].copy()
    result_rows: list[dict] = []
    prediction_rows: list[pd.DataFrame] = []
    breakdown_rows: list[dict] = []
    for name in finalists:
        numeric, categorical, hypothesis = experiments[name]
        trees = int(summary.loc[summary["experiment"].eq(name), "median_best_trees"].iloc[0])
        prediction = fit_final_xgb(train, test, numeric, categorical, trees, "poisson")
        values = score(test, prediction)
        result_rows.append({"model": name, "family": "XGBoost", "loss": "Poisson", "selection_role": "feature_finalist", "hypothesis": hypothesis, **values})
        output = test[["date", "segment", "market", "guests"]].copy()
        output["prediction"] = prediction
        output["model"] = name
        prediction_rows.append(output)
        for kind, grouper in (("market", "market"), ("month", test["date"].dt.to_period("M").astype(str))):
            temp = output.copy()
            temp["group"] = temp[grouper].to_numpy() if isinstance(grouper, str) else grouper.to_numpy()
            for group, part in temp.groupby("group", observed=True):
                breakdown_rows.append({"model": name, "breakdown": kind, "group": group, **score(part, part["prediction"].to_numpy())})
    return pd.DataFrame(result_rows), pd.concat(prediction_rows, ignore_index=True), pd.DataFrame(breakdown_rows), finalists


def paired_month_bootstrap(
    predictions: pd.DataFrame, baseline: str, challenger: str
) -> dict[str, float]:
    """Paired WMAPE uncertainty using months as correlation clusters."""
    selected = predictions[predictions["model"].isin([baseline, challenger])].copy()
    selected["month"] = selected["date"].dt.to_period("M").astype(str)
    selected["absolute_error"] = (selected["prediction"] - selected["guests"]).abs()
    monthly = (
        selected.groupby(["model", "month"], observed=True)
        .agg(absolute_error=("absolute_error", "sum"), actual=("guests", "sum"))
        .reset_index()
    )
    errors = monthly.pivot(index="month", columns="model", values="absolute_error")
    actual = monthly.groupby("month", observed=True)["actual"].first().reindex(errors.index)
    baseline_point = float(errors[baseline].sum() / actual.sum())
    challenger_point = float(errors[challenger].sum() / actual.sum())
    rng = np.random.default_rng(RANDOM_STATE)
    samples = rng.integers(0, len(errors), size=(20000, len(errors)))
    denominator = actual.to_numpy()[samples].sum(axis=1)
    baseline_sample = errors[baseline].to_numpy()[samples].sum(axis=1) / denominator
    challenger_sample = errors[challenger].to_numpy()[samples].sum(axis=1) / denominator
    difference = challenger_sample - baseline_sample
    return {
        "baseline_wmape": baseline_point,
        "challenger_wmape": challenger_point,
        "challenger_minus_baseline": challenger_point - baseline_point,
        "cluster_bootstrap_95pct_low": float(np.quantile(difference, 0.025)),
        "cluster_bootstrap_95pct_high": float(np.quantile(difference, 0.975)),
        "probability_challenger_better": float(np.mean(difference < 0)),
        "month_clusters": int(len(errors)),
        "bootstrap_samples": 20000,
    }


def benchmark_models(frame: pd.DataFrame, experiments: OrderedDict, summary: pd.DataFrame, selected_feature_model: str) -> pd.DataFrame:
    train = frame[frame["date"].lt(TEST_START)].copy()
    test = frame[frame["date"].between(TEST_START, TEST_END, inclusive="both")].copy()
    rows = []
    lean_num, lean_cat, _ = experiments["L0_lean_core"]
    baseline_name = "B0_current_baseline"
    selected_num, selected_cat, _ = experiments[baseline_name]
    linear_prediction = fit_final_linear(train, test, selected_num, selected_cat)
    rows.append({"model": "Linear regression (Ridge)", "features": baseline_name, "loss": "squared error", **score(test, linear_prediction)})

    trees = int(summary.loc[summary["experiment"].eq(baseline_name), "median_best_trees"].iloc[0])
    for label, objective in (("Pooled XGBoost Poisson", "poisson"), ("Pooled XGBoost log-target", "log_target"), ("Pooled XGBoost squared-error", "squared_error")):
        prediction = fit_final_xgb(train, test, selected_num, selected_cat, trees, objective)
        rows.append({"model": label, "features": baseline_name, "loss": objective, **score(test, prediction)})
    lean_trees = int(summary.loc[summary["experiment"].eq("L0_lean_core"), "median_best_trees"].iloc[0])
    lean_prediction = fit_final_xgb(train, test, lean_num, lean_cat, lean_trees, "poisson")
    rows.append({"model": "Lean pooled XGBoost Poisson", "features": "L0_lean_core", "loss": "poisson", **score(test, lean_prediction)})
    return pd.DataFrame(rows).sort_values("wmape")


def pct(value: float) -> str:
    return f"{value:.2%}"


def write_report(coverage: pd.DataFrame, correlations: pd.DataFrame, summary: pd.DataFrame, test_results: pd.DataFrame, benchmarks: pd.DataFrame, finalists: list[str], uncertainty: dict[str, float]) -> None:
    best = summary.iloc[0]
    best_safe = summary[~summary["experiment"].str.startswith(("P", "Q", "R", "D3", "D4", "D5"))].iloc[0]
    low_coverage = coverage[(coverage["segment"].eq("Overall")) & (coverage["coverage_pct"].lt(0.75))]
    lines = [
        "# Pooled Poisson feature-combination results",
        "",
        "Feature selection used two rolling chronological validation windows. The final test period (2024-08-01 to 2025-02-28) was opened only for predeclared anchors and validation-selected finalists.",
        "",
        "## Main result",
        "",
        f"- Best rolling-validation experiment: **{best['experiment']}** at **{pct(best['rolling_wmape'])}** WMAPE.",
        f"- Best schedule-safe experiment: **{best_safe['experiment']}** at **{pct(best_safe['rolling_wmape'])}** WMAPE.",
        f"- Finalists evaluated once on test: {', '.join(finalists)}.",
        "- **Final Poisson recommendation: keep `B0_current_baseline`.** The validation winner did not reproduce its gain on the untouched test period.",
        f"- Challenger minus baseline: {uncertainty['challenger_minus_baseline']:+.2%} WMAPE; paired month-cluster bootstrap 95% interval {uncertainty['cluster_bootstrap_95pct_low']:+.2%} to {uncertainty['cluster_bootstrap_95pct_high']:+.2%}.",
        "",
        "## Rolling-validation leaderboard",
        "",
        "| Rank | Experiment | Features | WMAPE | vs current | Domestic | International | Bias | Fold SD |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in summary.head(15).iterrows():
        lines.append(
            f"| {rank + 1} | {row['experiment']} | {int(row['feature_count_before_encoding'])} | {pct(row['rolling_wmape'])} | {row['delta_vs_current_baseline']:+.2%} | {pct(row['rolling_domestic_wmape'])} | {pct(row['rolling_international_wmape'])} | {pct(row['rolling_bias_pct'])} | {pct(row['fold_wmape_std'])} |"
        )
    lines += [
        "",
        "## Held-out test results",
        "",
        "| Model | WMAPE | Domestic | International | Bias | MAE | RMSE | Macro-market WMAPE | P90-market WMAPE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in test_results.sort_values("wmape").itertuples():
        lines.append(f"| {row.model} | {pct(row.wmape)} | {pct(row.domestic_wmape)} | {pct(row.international_wmape)} | {pct(row.bias_pct)} | {row.mae:.2f} | {row.rmse:.2f} | {pct(row.macro_market_wmape)} | {pct(row.p90_market_wmape)} |")
    lines += [
        "",
        "## Required model comparisons on the selected feature definition",
        "",
        "| Model | Features | WMAPE | Domestic | International | Bias | MAE | RMSE |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in benchmarks.itertuples():
        lines.append(f"| {row.model} | {row.features} | {pct(row.wmape)} | {pct(row.domestic_wmape)} | {pct(row.international_wmape)} | {pct(row.bias_pct)} | {row.mae:.2f} | {row.rmse:.2f} |")
    lines += [
        "",
        "## Feature definitions",
        "",
        "- **Final pooled Poisson baseline:** linear time trend; annual sine and cosine; weekend; new arrivals; same-day guests plus missing indicator; previous-year total guests; previous-year new arrivals; year-over-year arrival ratio; market; month; day of week; domestic/international segment.",
        "- **Validation challenger:** the complete baseline plus average weekly flight frequency and global departure-country seat concentration.",
        "- **Lean comparison:** trend; new arrivals; same-day guests plus missing indicator; previous-year total guests; market; segment; month; day of week.",
        "- **Compact scheduled comparison:** lean/historical core plus total seats, year-over-year seat change, active-route count and seat concentration.",
        "",
        "## Data verification findings",
        "",
        f"- {len(low_coverage)} candidate features have less than 75% overall non-null coverage; see `feature_coverage.csv`.",
        "- Global aviation values exist at monthly grain and are repeated over daily hotel rows. Rolling time validation, not random row splitting, is therefore mandatory.",
        "- Passenger load factor and passenger shares are realized historical values. They are conditional model inputs unless a planned/forecast value is provided at scenario time.",
        "- Departure-origin features were excluded from this pooled search because departure country is not the same entity as hotel guest nationality.",
        "- Highly related pairs are documented in `feature_correlations.csv`; correlation is measured over unique months rather than repeated daily rows.",
        "",
        "## Interpretation rule",
        "",
        "The production recommendation prioritizes rolling validation, forecast-time availability, domestic/international stability, and scenario meaning. The held-out test is evidence, not a new feature-selection loop.",
        "",
    ]
    (OUTPUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = add_derived_features(shared.load_model_frame())
    frame["month"] = frame["date"].dt.to_period("M").dt.to_timestamp()
    experiments = definitions()
    all_numeric = unique([feature for numeric, _, _ in experiments.values() for feature in numeric])
    coverage = coverage_table(frame, all_numeric)
    coverage.to_csv(OUTPUT / "feature_coverage.csv", index=False)
    correlation_features = unique(list(SCHEDULED.values()) + list(PASSENGER.values()) + list(DERIVED.values()))
    correlations = correlation_table(frame, correlation_features)
    correlations.to_csv(OUTPUT / "feature_correlations.csv", index=False)

    fold_results, summary = rolling_search(frame, experiments)
    fold_results.to_csv(OUTPUT / "rolling_fold_results.csv", index=False)
    summary.to_csv(OUTPUT / "rolling_feature_leaderboard.csv", index=False)

    test_results, predictions, breakdowns, finalists = evaluate_test_finalists(frame, experiments, summary)
    test_results.to_csv(OUTPUT / "heldout_test_finalists.csv", index=False)
    predictions.to_csv(OUTPUT / "heldout_test_predictions.csv", index=False)
    breakdowns.to_csv(OUTPUT / "heldout_test_breakdowns.csv", index=False)
    uncertainty = paired_month_bootstrap(
        predictions, "B0_current_baseline", str(summary.iloc[0]["experiment"])
    )
    (OUTPUT / "paired_month_bootstrap.json").write_text(
        json.dumps(uncertainty, indent=2), encoding="utf-8"
    )

    # The primary selected definition is the best schedule-safe candidate by rolling validation.
    safe = summary[~summary["experiment"].str.startswith(("P", "Q", "R", "D3", "D4", "D5"))]
    selected = str(safe.iloc[0]["experiment"])
    benchmarks = benchmark_models(frame, experiments, summary, selected)
    benchmarks.to_csv(OUTPUT / "model_benchmarks.csv", index=False)
    write_report(coverage, correlations, summary, test_results, benchmarks, finalists, uncertainty)
    metadata = {
        "selection_metric": "row-weighted WMAPE across two rolling chronological validation folds",
        "test_period": [str(TEST_START.date()), str(TEST_END.date())],
        "experiment_count": len(experiments),
        "selected_schedule_safe_feature_definition": selected,
        "final_poisson_recommendation": "B0_current_baseline",
        "finalists": finalists,
        "random_state": RANDOM_STATE,
        "no_origin_to_nationality_exact_match": True,
    }
    (OUTPUT / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("\nTop rolling-validation results")
    print(summary[["experiment", "rolling_wmape", "rolling_domestic_wmape", "rolling_international_wmape"]].head(12).to_string(index=False))
    print("\nHeld-out finalists")
    print(test_results[["model", "wmape", "domestic_wmape", "international_wmape", "bias_pct"]].sort_values("wmape").to_string(index=False))
    print("\nBenchmarks")
    print(benchmarks[["model", "features", "wmape", "domestic_wmape", "international_wmape", "bias_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
