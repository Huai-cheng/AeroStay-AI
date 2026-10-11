"""Evaluate XGBoost losses against isolated and combined ETL feature groups."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier, XGBRegressor


ROOT = Path(__file__).resolve().parents[2]
ETL_OUTPUT = ROOT / "artifacts" / "etl"
OUTPUT = ROOT / "artifacts" / "feature_group_xgboost"
RANDOM_STATE = 20261010
TUNE_END = pd.Timestamp("2024-01-31")
VALIDATION_START = pd.Timestamp("2024-02-01")
VALIDATION_END = pd.Timestamp("2024-07-31")
OFFLINE_START = pd.Timestamp("2024-08-01")
OFFLINE_END = pd.Timestamp("2025-02-28")
EPS = 1e-9

BASE_NUMERIC = [
    "linear_time_trend_days",
    "annual_seasonal_sine",
    "annual_seasonal_cosine",
    "weekend_indicator",
    "new_arrivals",
    "same_day_guests",
    "same_day_guests_missing_indicator",
    "previous_year_total_guests",
    "previous_year_new_arrivals",
    "year_over_year_arrival_ratio",
]
BASE_CATEGORICAL = ["market", "month_category", "day_of_week_category"]

GROUPS = OrderedDict(
    [
        ("E0_baseline", []),
        ("E1_historical_extension", ["previous_year_same_day_guests"]),
        (
            "E2_capacity_network",
            [
                "global_total_scheduled_seats",
                "global_average_weekly_flight_frequency",
                "global_active_route_count",
                "global_new_route_count",
                "global_discontinued_route_count",
                "global_departure_country_count",
                "global_year_over_year_seat_change",
                "global_year_over_year_frequency_change",
            ],
        ),
        (
            "E3_passenger_composition",
            [
                "global_passenger_load_factor",
                "global_point_to_point_passenger_share",
                "global_transfer_passenger_share",
                "global_transit_passenger_share",
            ],
        ),
        (
            "E4_origin_market_mix",
            [
                "global_origin_market_seat_concentration",
                "origin_match_available",
                "origin_total_scheduled_seats",
                "origin_average_weekly_flight_frequency",
                "origin_active_route_count",
                "origin_new_route_count",
                "origin_discontinued_route_count",
                "origin_departure_country_seat_share",
                "origin_departure_country_passenger_share",
                "origin_year_over_year_seat_change",
                "origin_year_over_year_frequency_change",
            ],
        ),
    ]
)
LOSSES = ("squared_error", "poisson", "log_target", "binned_cross_entropy")
SCOPES = ("domestic", "international", "pooled")


def wmape(actual: np.ndarray, prediction: np.ndarray) -> float:
    return float(np.abs(actual - prediction).sum() / max(np.abs(actual).sum(), EPS))


def ensure_etl() -> None:
    required = [
        ETL_OUTPUT / "hotel_daily.csv",
        ETL_OUTPUT / "flight_origin_monthly.csv",
        ETL_OUTPUT / "flight_global_monthly.csv",
    ]
    if not all(path.exists() for path in required):
        subprocess.run(
            [sys.executable, str(ROOT / "etl" / "build_feature_tables.py")],
            check=True,
            cwd=ROOT,
        )


def load_model_frame() -> pd.DataFrame:
    ensure_etl()
    hotel = pd.read_csv(ETL_OUTPUT / "hotel_daily.csv", parse_dates=["date"])
    hotel["month"] = hotel["date"].dt.to_period("M").dt.to_timestamp()
    global_monthly = pd.read_csv(ETL_OUTPUT / "flight_global_monthly.csv", parse_dates=["month"])
    global_monthly = global_monthly.add_prefix("global_").rename(columns={"global_month": "month"})
    origin = pd.read_csv(ETL_OUTPUT / "flight_origin_monthly.csv", parse_dates=["month"])
    origin = origin.add_prefix("origin_").rename(
        columns={"origin_month": "month", "origin_departure_country": "market"}
    )
    frame = hotel.merge(global_monthly, on="month", how="left", validate="many_to_one")
    frame = frame.merge(origin, on=["month", "market"], how="left", validate="many_to_one")
    origin_value_columns = [column for column in origin.columns if column not in {"month", "market"}]
    frame["origin_match_available"] = frame[origin_value_columns].notna().any(axis=1).astype("int8")
    frame["segment"] = frame["segment"].astype(str)
    frame["market"] = frame["market"].astype(str)
    return frame


def split(frame: pd.DataFrame, scope: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if scope == "domestic":
        frame = frame[frame["segment"].eq("Domestic")].copy()
    elif scope == "international":
        frame = frame[frame["segment"].eq("International")].copy()
    tune = frame[frame["date"].le(TUNE_END)].copy()
    validation = frame[
        frame["date"].between(VALIDATION_START, VALIDATION_END, inclusive="both")
    ].copy()
    offline = frame[frame["date"].between(OFFLINE_START, OFFLINE_END, inclusive="both")].copy()
    if tune.empty or validation.empty or offline.empty:
        raise ValueError(f"Empty chronological partition for {scope}")
    if not tune["date"].max() < validation["date"].min() <= validation["date"].max() < offline["date"].min():
        raise ValueError(f"Temporal split overlap for {scope}")
    return tune, validation, offline


def preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        (
                            "impute",
                            SimpleImputer(
                                strategy="median", add_indicator=True, keep_empty_features=True
                            ),
                        )
                    ]
                ),
                numeric,
            ),
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


def params() -> dict:
    return {
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
        "early_stopping_rounds": 75,
    }


def make_bins(target: np.ndarray, requested_bins: int = 12) -> tuple[np.ndarray, np.ndarray]:
    _, edges = pd.qcut(target, q=requested_bins, retbins=True, duplicates="drop")
    edges = np.unique(np.asarray(edges, dtype=float))
    edges[0] = -np.inf
    edges[-1] = np.inf
    labels = np.digitize(target, edges[1:-1], right=True)
    representatives = np.array(
        [np.median(target[labels == label]) for label in range(len(edges) - 1)], dtype=float
    )
    return edges, representatives


def classify(target: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.digitize(target, edges[1:-1], right=True).astype(int)


def fit_predict(
    tune: pd.DataFrame,
    validation: pd.DataFrame,
    offline: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    loss: str,
) -> tuple[np.ndarray, np.ndarray, int, int | None]:
    features = numeric + categorical
    tune_transformer = preprocessor(numeric, categorical)
    x_tune = tune_transformer.fit_transform(tune[features])
    x_validation = tune_transformer.transform(validation[features])
    y_tune = tune["guests"].to_numpy(float)
    y_validation = validation["guests"].to_numpy(float)
    model_params = params()
    bin_count = None

    if loss == "binned_cross_entropy":
        edges, representatives = make_bins(y_tune)
        y_tune_fit = classify(y_tune, edges)
        y_validation_fit = classify(y_validation, edges)
        model = XGBClassifier(
            objective="multi:softprob",
            num_class=len(representatives),
            eval_metric="mlogloss",
            **model_params,
        )
        model.fit(x_tune, y_tune_fit, eval_set=[(x_validation, y_validation_fit)], verbose=False)
        validation_prediction = model.predict_proba(x_validation) @ representatives
        bin_count = len(representatives)
    else:
        objective = "count:poisson" if loss == "poisson" else "reg:squarederror"
        if loss == "log_target":
            y_tune_fit = np.log1p(y_tune)
            y_validation_fit = np.log1p(y_validation)
            eval_metric = "rmse"
        else:
            y_tune_fit = y_tune
            y_validation_fit = y_validation
            eval_metric = "mae"
        model = XGBRegressor(objective=objective, eval_metric=eval_metric, **model_params)
        model.fit(x_tune, y_tune_fit, eval_set=[(x_validation, y_validation_fit)], verbose=False)
        validation_prediction = model.predict(x_validation)
        if loss == "log_target":
            validation_prediction = np.expm1(validation_prediction)

    best_trees = int(model.best_iteration) + 1
    final_train = pd.concat([tune, validation], ignore_index=True)
    final_transformer = preprocessor(numeric, categorical)
    x_final = final_transformer.fit_transform(final_train[features])
    x_offline = final_transformer.transform(offline[features])
    y_final = final_train["guests"].to_numpy(float)
    final_params = params()
    final_params.pop("early_stopping_rounds")
    final_params["n_estimators"] = best_trees

    if loss == "binned_cross_entropy":
        final_edges, final_representatives = make_bins(y_final)
        final_model = XGBClassifier(
            objective="multi:softprob",
            num_class=len(final_representatives),
            eval_metric="mlogloss",
            **final_params,
        )
        final_model.fit(x_final, classify(y_final, final_edges), verbose=False)
        offline_prediction = final_model.predict_proba(x_offline) @ final_representatives
        bin_count = len(final_representatives)
    else:
        objective = "count:poisson" if loss == "poisson" else "reg:squarederror"
        y_final_fit = np.log1p(y_final) if loss == "log_target" else y_final
        final_model = XGBRegressor(objective=objective, **final_params)
        final_model.fit(x_final, y_final_fit, verbose=False)
        offline_prediction = final_model.predict(x_offline)
        if loss == "log_target":
            offline_prediction = np.expm1(offline_prediction)

    return (
        np.clip(np.asarray(validation_prediction), 0.0, None),
        np.clip(np.asarray(offline_prediction), 0.0, None),
        best_trees,
        bin_count,
    )


def metrics(frame: pd.DataFrame, prediction: np.ndarray) -> dict[str, float]:
    actual = frame["guests"].to_numpy(float)
    error = prediction - actual
    scored = frame[["date", "market", "guests"]].copy()
    scored["prediction"] = prediction
    market_scores = [
        wmape(part["guests"].to_numpy(float), part["prediction"].to_numpy(float))
        for _, part in scored.groupby("market", observed=True)
    ]
    return {
        "rows": int(len(frame)),
        "wmape": wmape(actual, prediction),
        "bias_pct": float(error.sum() / max(actual.sum(), EPS)),
        "mae": float(mean_absolute_error(actual, prediction)),
        "rmse": float(math.sqrt(mean_squared_error(actual, prediction))),
        "r2": float(r2_score(actual, prediction)),
        "macro_market_wmape": float(np.mean(market_scores)),
        "median_market_wmape": float(np.median(market_scores)),
        "p90_market_wmape": float(np.quantile(market_scores, 0.90)),
    }


def breakdowns(
    frame: pd.DataFrame,
    prediction: np.ndarray,
    run_id: str,
    scope: str,
    experiment: str,
    loss: str,
) -> tuple[list[dict], list[dict]]:
    scored = frame[["date", "market", "guests"]].copy()
    scored["prediction"] = prediction
    market_rows = []
    for market, part in scored.groupby("market", observed=True):
        values = metrics(part.assign(market=market), part["prediction"].to_numpy())
        market_rows.append(
            {"run_id": run_id, "scope": scope, "experiment": experiment, "loss": loss, "market": market, **values}
        )
    month_rows = []
    scored["month"] = scored["date"].dt.to_period("M").astype(str)
    for month, part in scored.groupby("month", observed=True):
        values = metrics(part, part["prediction"].to_numpy())
        month_rows.append(
            {"run_id": run_id, "scope": scope, "experiment": experiment, "loss": loss, "month": month, **values}
        )
    return market_rows, month_rows


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "etl" / "build_feature_tables.py")], check=True, cwd=ROOT)
    frame = load_model_frame()
    history: list[dict] = []
    market_history: list[dict] = []
    month_history: list[dict] = []
    run_number = 0

    for scope in SCOPES:
        tune, validation, offline = split(frame, scope)
        categorical = BASE_CATEGORICAL + (["segment"] if scope == "pooled" else [])
        for experiment, additions in GROUPS.items():
            numeric = BASE_NUMERIC + additions
            for loss in LOSSES:
                run_number += 1
                run_id = f"R{run_number:03d}"
                started = time.perf_counter()
                record = {
                    "run_id": run_id,
                    "scope": scope,
                    "mode": "isolated",
                    "experiment": experiment,
                    "loss": loss,
                    "added_features": "|".join(additions),
                    "numeric_features": "|".join(numeric),
                    "categorical_features": "|".join(categorical),
                    "tune_end": str(TUNE_END.date()),
                    "validation_start": str(VALIDATION_START.date()),
                    "validation_end": str(VALIDATION_END.date()),
                    "offline_start": str(OFFLINE_START.date()),
                    "offline_end": str(OFFLINE_END.date()),
                    "random_state": RANDOM_STATE,
                }
                try:
                    validation_prediction, offline_prediction, best_trees, bin_count = fit_predict(
                        tune, validation, offline, numeric, categorical, loss
                    )
                    validation_metrics = metrics(validation, validation_prediction)
                    offline_metrics = metrics(offline, offline_prediction)
                    record.update({f"validation_{key}": value for key, value in validation_metrics.items()})
                    record.update({f"offline_{key}": value for key, value in offline_metrics.items()})
                    record.update(
                        {
                            "best_trees": best_trees,
                            "bin_count": bin_count,
                            "status": "ok",
                            "seconds": round(time.perf_counter() - started, 3),
                        }
                    )
                    market_rows, month_rows = breakdowns(
                        offline, offline_prediction, run_id, scope, experiment, loss
                    )
                    market_history.extend(market_rows)
                    month_history.extend(month_rows)
                    print(
                        f"{run_id} {scope} {experiment} {loss}: "
                        f"val={validation_metrics['wmape']:.4%} offline={offline_metrics['wmape']:.4%}",
                        flush=True,
                    )
                except Exception as exc:
                    record.update(
                        {
                            "status": "failed",
                            "error": repr(exc),
                            "seconds": round(time.perf_counter() - started, 3),
                        }
                    )
                    print(f"{run_id} FAILED: {exc!r}", flush=True)
                history.append(record)
                pd.DataFrame(history).to_csv(OUTPUT / "experiment_history.csv", index=False)

    results = pd.DataFrame(history)
    ok = results[results["status"].eq("ok")].copy()
    ok.to_csv(OUTPUT / "loss_by_feature_group.csv", index=False)
    pd.DataFrame(market_history).to_csv(OUTPUT / "market_metrics.csv", index=False)
    pd.DataFrame(month_history).to_csv(OUTPUT / "monthly_metrics.csv", index=False)

    baseline = ok[ok["experiment"].eq("E0_baseline")][
        ["scope", "loss", "validation_wmape"]
    ].rename(columns={"validation_wmape": "baseline_validation_wmape"})
    progression = ok.merge(baseline, on=["scope", "loss"], how="left")
    progression["validation_wmape_change"] = (
        progression["validation_wmape"] - progression["baseline_validation_wmape"]
    )
    progression["improved_validation"] = progression["validation_wmape_change"].lt(0)
    progression.to_csv(OUTPUT / "feature_group_progression.csv", index=False)

    best = ok.sort_values("validation_wmape").groupby("scope", observed=True).head(1)
    metadata = {
        "run_count": int(len(results)),
        "successful_runs": int(len(ok)),
        "failed_runs": int(len(results) - len(ok)),
        "selection_metric": "validation_wmape",
        "external_calendar_group": "skipped: no authoritative source supplied",
        "best_by_scope": best[
            ["scope", "run_id", "experiment", "loss", "validation_wmape", "offline_wmape"]
        ].to_dict(orient="records"),
    }
    (OUTPUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    lines = [
        "# Feature-group XGBoost experiment report",
        "",
        "Selection uses the pre-offline validation WMAPE. Offline values are reported for evidence, not used to select the winner.",
        "",
        "## Best validation-selected run by scope",
        "",
        "| Scope | Run | Feature experiment | Loss | Validation WMAPE | Offline WMAPE |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in best.itertuples():
        lines.append(
            f"| {row.scope} | {row.run_id} | {row.experiment} | {row.loss} | "
            f"{row.validation_wmape:.2%} | {row.offline_wmape:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- E1 through E4 are isolated additions to E0, not a cumulative final model.",
            "- External event and holiday features were not trained because no authoritative source is present.",
            "- Passenger composition contains historically realized values and therefore fails the production-availability gate unless scenario-generated or externally forecast.",
            "- Binned cross entropy is a diagnostic classification formulation and loses exact count resolution.",
            "",
        ]
    )
    (OUTPUT / "EXPERIMENT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nBest by validation")
    print(best[["scope", "run_id", "experiment", "loss", "validation_wmape", "offline_wmape"]].to_string(index=False))


if __name__ == "__main__":
    main()

