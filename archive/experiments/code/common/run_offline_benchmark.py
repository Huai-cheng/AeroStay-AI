"""Train and compare isolated hotel-night forecasting approaches.

The script intentionally reads only the supplied raw workbooks.  It does not import or
inspect the repository's existing solution.  Every approach is evaluated on the same
locked chronological holdout: 2024-08-01 through 2025-02-28.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUTPUT = ROOT / "artifacts" / "offline_metrics"
TRAIN_END = pd.Timestamp("2024-07-31")
TEST_START = pd.Timestamp("2024-08-01")
TEST_END = pd.Timestamp("2025-02-28")
EPS = 1e-9
RANDOM_STATE = 20261010

DEMAND_FEATURES = [
    "new_arrivals",
    "same_day_guests",
    "same_day_missing",
    "prior_year_guests",
    "prior_year_arrivals",
    "arrivals_yoy_ratio",
]

AVIATION_FEATURES = [
    "flight_total_seats",
    "flight_total_pax",
    "flight_total_p2p",
    "flight_total_transfer",
    "flight_total_transit",
    "flight_load_factor",
    "flight_route_rows",
    "flight_country_count",
    "flight_city_count",
    "flight_airline_count",
    "market_total_seats",
    "market_total_pax",
    "market_total_p2p",
    "market_total_transfer",
    "market_total_transit",
    "market_load_factor",
    "market_has_direct_flight",
]

CALENDAR_NUMERIC = [
    "trend_days",
    "dow",
    "month",
    "day_of_year_sin",
    "day_of_year_cos",
    "is_weekend",
]

CATEGORICAL = ["market", "segment", "month_cat", "dow_cat"]


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
        for c in result.columns
    ]
    return result


def load_hotel_data() -> pd.DataFrame:
    domestic = normalize_columns(pd.read_excel(DATA / "data domestic_train.xlsx"))
    international = normalize_columns(pd.read_excel(DATA / "data international_train.xlsx"))

    domestic["segment"] = "Domestic"
    domestic["market"] = "DOMESTIC"
    international["segment"] = "International"
    international["market"] = international["nationality"].astype(str).str.upper().str.strip()

    keep = ["date", "guests", "new_arrivals", "same_day_guests", "segment", "market"]
    combined = pd.concat([domestic[keep], international[keep]], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values(["date", "segment", "market"]).reset_index(drop=True)
    combined["guests"] = pd.to_numeric(combined["guests"], errors="coerce")
    combined["new_arrivals"] = pd.to_numeric(combined["new_arrivals"], errors="coerce")
    combined["same_day_missing"] = combined["same_day_guests"].isna().astype("int8")
    combined["same_day_guests"] = pd.to_numeric(combined["same_day_guests"], errors="coerce")
    return combined


def load_flight_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    flights = normalize_columns(pd.read_excel(DATA / "flight_data.xlsx"))
    flights["date"] = pd.to_datetime(flights["date"])
    flights["market"] = flights["departure_country_name"].astype(str).str.upper().str.strip()

    values = ["total_seats", "total_pax", "total_p2p", "total_transfer", "total_transit"]
    for col in values:
        flights[col] = pd.to_numeric(flights[col], errors="coerce").fillna(0.0)

    global_sum = flights.groupby("date", observed=True)[values].sum().add_prefix("flight_")
    global_counts = flights.groupby("date", observed=True).agg(
        flight_route_rows=("departure_city", "size"),
        flight_country_count=("departure_country_name", "nunique"),
        flight_city_count=("departure_city", "nunique"),
        flight_airline_count=("airline_name", "nunique"),
    )
    global_daily = global_sum.join(global_counts).reset_index()
    global_daily["flight_load_factor"] = (
        global_daily["flight_total_pax"] / global_daily["flight_total_seats"].clip(lower=1.0)
    )

    market_daily = (
        flights.groupby(["date", "market"], observed=True)[values]
        .sum()
        .add_prefix("market_")
        .reset_index()
    )
    market_daily["market_load_factor"] = (
        market_daily["market_total_pax"] / market_daily["market_total_seats"].clip(lower=1.0)
    )
    market_daily["market_has_direct_flight"] = 1
    return global_daily, market_daily


def add_features(hotel: pd.DataFrame, flight_global: pd.DataFrame, flight_market: pd.DataFrame) -> pd.DataFrame:
    data = hotel.merge(flight_global, on="date", how="left").merge(
        flight_market, on=["date", "market"], how="left"
    )

    for col in AVIATION_FEATURES:
        if col.startswith("market_"):
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)

    data["trend_days"] = (data["date"] - data["date"].min()).dt.days
    data["dow"] = data["date"].dt.dayofweek
    data["month"] = data["date"].dt.month
    data["month_cat"] = data["month"].astype(str)
    data["dow_cat"] = data["dow"].astype(str)
    data["is_weekend"] = data["dow"].isin([5, 6]).astype("int8")
    angle = 2.0 * math.pi * data["date"].dt.dayofyear / 365.25
    data["day_of_year_sin"] = np.sin(angle)
    data["day_of_year_cos"] = np.cos(angle)

    # Compute the source date from each forecast row.  Shifting all history forward
    # would make 2024-02-29 and 2024-02-28 both land on 2025-02-28.
    data["prior_date"] = data["date"] - pd.DateOffset(years=1)
    history = data[["date", "market", "segment", "guests", "new_arrivals"]].copy()
    history = history.rename(
        columns={
            "date": "prior_date",
            "guests": "prior_year_guests",
            "new_arrivals": "prior_year_arrivals",
        }
    )
    data = data.merge(
        history,
        on=["prior_date", "market", "segment"],
        how="left",
        validate="many_to_one",
    )
    data["arrivals_yoy_ratio"] = (
        data["new_arrivals"] / data["prior_year_arrivals"].clip(lower=1.0)
    )
    return data


def split_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = data[data["date"] <= TRAIN_END].copy()
    test = data[(data["date"] >= TEST_START) & (data["date"] <= TEST_END)].copy()
    expected = pd.date_range(TEST_START, TEST_END, freq="D")
    actual = pd.DatetimeIndex(test["date"].drop_duplicates().sort_values())
    if not actual.equals(expected):
        raise RuntimeError("Offline test dates do not exactly match the locked 212-day horizon")
    if train["date"].max() >= test["date"].min():
        raise RuntimeError("Temporal leakage: training and offline test overlap")
    return train, test


def sklearn_preprocessor(numeric: list[str], spline: bool = False) -> ColumnTransformer:
    if spline:
        numeric_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
                ("scale", StandardScaler(with_mean=False)),
            ]
        )
    else:
        numeric_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler(with_mean=False)),
            ]
        )
    category_pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric_pipe, numeric), ("category", category_pipe, CATEGORICAL)]
    )


def fit_sklearn_model(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: list[str],
    estimator,
    *,
    residual: bool = False,
    spline: bool = False,
) -> np.ndarray:
    fit_rows = train["prior_year_guests"].notna() if residual else pd.Series(True, index=train.index)
    train_fit = train.loc[fit_rows]
    target = train_fit["guests"]
    if residual:
        target = target - train_fit["prior_year_guests"]
    model = Pipeline(
        [("features", sklearn_preprocessor(numeric, spline=spline)), ("model", estimator)]
    )
    model.fit(train_fit[numeric + CATEGORICAL], target)
    prediction = model.predict(test[numeric + CATEGORICAL])
    if residual:
        prediction = test["prior_year_guests"].to_numpy() + prediction
    return np.clip(prediction, 0.0, None)


def fit_by_segment(
    train: pd.DataFrame,
    test: pd.DataFrame,
    fitter: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
) -> np.ndarray:
    """Fit domestic separately and pool all international markets together."""
    prediction = pd.Series(index=test.index, dtype=float)
    for segment in ("Domestic", "International"):
        train_part = train[train["segment"].eq(segment)]
        test_part = test[test["segment"].eq(segment)]
        prediction.loc[test_part.index] = fitter(train_part, test_part)
    if prediction.isna().any():
        raise RuntimeError("Segment model left prediction rows unfilled")
    return prediction.loc[test.index].to_numpy()


def xgb_estimator(objective: str = "reg:squarederror") -> XGBRegressor:
    return XGBRegressor(
        objective=objective,
        n_estimators=650,
        learning_rate=0.035,
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


def seasonal_naive(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    fallback = train.groupby(["segment", "market", "month"], observed=True)["guests"].median()
    values = test["prior_year_guests"].copy()
    missing = values.isna()
    if missing.any():
        values.loc[missing] = test.loc[missing].join(
            fallback.rename("fallback"), on=["segment", "market", "month"]
        )["fallback"]
    values = values.fillna(train["guests"].median())
    return values.clip(lower=0).to_numpy()


def regularized_linear(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES + AVIATION_FEATURES
    return fit_by_segment(
        train,
        test,
        lambda tr, te: fit_sklearn_model(tr, te, features, Ridge(alpha=25.0)),
    )


def demand_xgboost(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES
    return fit_by_segment(
        train, test, lambda tr, te: fit_sklearn_model(tr, te, features, xgb_estimator())
    )


def aviation_xgboost(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + ["prior_year_guests"] + AVIATION_FEATURES
    return fit_by_segment(
        train, test, lambda tr, te: fit_sklearn_model(tr, te, features, xgb_estimator())
    )


def hybrid_residual_xgboost(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES + AVIATION_FEATURES
    return fit_by_segment(
        train,
        test,
        lambda tr, te: fit_sklearn_model(tr, te, features, xgb_estimator(), residual=True),
    )


def pooled_catboost(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES + AVIATION_FEATURES + CATEGORICAL
    def fit_one(train_part: pd.DataFrame, test_part: pd.DataFrame) -> np.ndarray:
        fit_rows = train_part["prior_year_guests"].notna()
        train_fit = train_part.loc[fit_rows, features].copy()
        test_fit = test_part[features].copy()
        for col in CATEGORICAL:
            train_fit[col] = train_fit[col].fillna("UNKNOWN").astype(str)
            test_fit[col] = test_fit[col].fillna("UNKNOWN").astype(str)
        target = (
            train_part.loc[fit_rows, "guests"] - train_part.loc[fit_rows, "prior_year_guests"]
        )
        model = CatBoostRegressor(
            loss_function="RMSE",
            iterations=650,
            learning_rate=0.035,
            depth=7,
            l2_leaf_reg=10.0,
            random_seed=RANDOM_STATE,
            verbose=False,
            allow_writing_files=False,
        )
        model.fit(train_fit, target, cat_features=CATEGORICAL)
        return np.clip(
            test_part["prior_year_guests"].to_numpy() + model.predict(test_fit), 0.0, None
        )

    return fit_by_segment(train, test, fit_one)


def lightgbm_residual(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES + AVIATION_FEATURES
    estimator = LGBMRegressor(
        objective="regression",
        n_estimators=650,
        learning_rate=0.035,
        max_depth=6,
        num_leaves=31,
        min_child_samples=40,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=10.0,
        reg_alpha=0.1,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbosity=-1,
    )
    return fit_by_segment(
        train,
        test,
        lambda tr, te: fit_sklearn_model(tr, te, features, estimator, residual=True),
    )


def interpretable_gam(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    features = CALENDAR_NUMERIC + DEMAND_FEATURES + AVIATION_FEATURES
    return fit_by_segment(
        train,
        test,
        lambda tr, te: fit_sklearn_model(tr, te, features, Ridge(alpha=50.0), spline=True),
    )


def hierarchical_rate_model(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    fit = train[train["new_arrivals"].notna() & (train["new_arrivals"] >= 0)].copy()
    global_rate = fit["guests"].sum() / fit["new_arrivals"].sum()
    by_group = fit.groupby(["segment", "market", "month"], observed=True).agg(
        group_guests=("guests", "sum"), group_arrivals=("new_arrivals", "sum")
    )
    alpha = 500.0
    by_group["rate"] = (
        by_group["group_guests"] + alpha * global_rate
    ) / (by_group["group_arrivals"] + alpha)
    lookup = test.join(by_group["rate"], on=["segment", "market", "month"])["rate"].fillna(global_rate)
    conversion_prediction = test["new_arrivals"].fillna(0).to_numpy() * lookup.to_numpy()
    seasonal = test["prior_year_guests"].to_numpy()
    return np.clip(0.70 * conversion_prediction + 0.30 * seasonal, 0.0, None)


def metric_values(
    actual: np.ndarray,
    predicted: np.ndarray,
    naive: np.ndarray,
    mase_scale: float,
) -> dict[str, float]:
    error = predicted - actual
    naive_mae = np.mean(np.abs(actual - naive))
    model_mae = np.mean(np.abs(error))
    return {
        "rows": int(len(actual)),
        "actual_total": float(np.sum(actual)),
        "predicted_total": float(np.sum(predicted)),
        "wmape": float(np.sum(np.abs(error)) / max(np.sum(np.abs(actual)), EPS)),
        "bias_pct": float(np.sum(error) / max(np.sum(actual), EPS)),
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
        "mase": float(model_mae / max(mase_scale, EPS)),
        "relative_mae_vs_seasonal_naive": float(model_mae / max(naive_mae, EPS)),
        "r2": float(r2_score(actual, predicted)),
        "total_error": float(np.sum(error)),
    }


def evaluate_predictions(
    frame: pd.DataFrame,
    model_name: str,
    mase_scales: dict[str, float],
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    records: list[dict] = []
    naive = frame["prior_year_guests"].to_numpy()
    groups = {
        "combined": np.ones(len(frame), dtype=bool),
        "domestic": frame["segment"].eq("Domestic").to_numpy(),
        "international": frame["segment"].eq("International").to_numpy(),
    }
    for scope, mask in groups.items():
        values = metric_values(
            frame.loc[mask, "guests"].to_numpy(),
            frame.loc[mask, "prediction"].to_numpy(),
            naive[mask],
            mase_scales[scope],
        )
        records.append({"model": model_name, "scope": scope, **values})

    international = frame[frame["segment"].eq("International")]
    market_metrics = []
    for market, part in international.groupby("market", observed=True):
        values = metric_values(
            part["guests"].to_numpy(),
            part["prediction"].to_numpy(),
            part["prior_year_guests"].to_numpy(),
            mase_scales["international"],
        )
        market_metrics.append({"model": model_name, "market": market, **values})
    market_frame = pd.DataFrame(market_metrics)
    for record in records:
        if record["scope"] == "international" and not market_frame.empty:
            record["macro_market_wmape"] = float(market_frame["wmape"].mean())
            record["median_market_wmape"] = float(market_frame["wmape"].median())
            record["p90_market_wmape"] = float(market_frame["wmape"].quantile(0.90))
        else:
            record["macro_market_wmape"] = np.nan
            record["median_market_wmape"] = np.nan
            record["p90_market_wmape"] = np.nan
    month_metrics = []
    for month, part in frame.groupby(frame["date"].dt.to_period("M"), observed=True):
        values = metric_values(
            part["guests"].to_numpy(),
            part["prediction"].to_numpy(),
            part["prior_year_guests"].to_numpy(),
            mase_scales["combined"],
        )
        month_metrics.append({"model": model_name, "month": str(month), **values})
    return records, market_frame, pd.DataFrame(month_metrics)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hotel = load_hotel_data()
    flight_global, flight_market = load_flight_features()
    data = add_features(hotel, flight_global, flight_market)
    train, test = split_data(data)

    train_with_scale = train[train["prior_year_guests"].notna()].copy()
    train_with_scale["seasonal_abs_error"] = (
        train_with_scale["guests"] - train_with_scale["prior_year_guests"]
    ).abs()
    mase_scales = {
        "combined": float(train_with_scale["seasonal_abs_error"].mean()),
        "domestic": float(
            train_with_scale.loc[
                train_with_scale["segment"].eq("Domestic"), "seasonal_abs_error"
            ].mean()
        ),
        "international": float(
            train_with_scale.loc[
                train_with_scale["segment"].eq("International"), "seasonal_abs_error"
            ].mean()
        ),
    }

    metadata = {
        "train_start": str(train["date"].min().date()),
        "train_end": str(train["date"].max().date()),
        "offline_test_start": str(test["date"].min().date()),
        "offline_test_end": str(test["date"].max().date()),
        "offline_test_unique_dates": int(test["date"].nunique()),
        "train_rows": int(len(train)),
        "offline_test_rows": int(len(test)),
        "feature_availability_note": (
            "Metrics use future regressors supplied in the historical workbooks. "
            "They estimate provided-feature forecast performance, not causal effects."
        ),
    }
    (OUTPUT / "benchmark_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    runners: list[tuple[str, Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]]] = [
        ("seasonal_naive", seasonal_naive),
        ("regularized_linear", regularized_linear),
        ("demand_xgboost", demand_xgboost),
        ("aviation_xgboost", aviation_xgboost),
        ("hybrid_residual_xgboost", hybrid_residual_xgboost),
        ("pooled_catboost", pooled_catboost),
        ("lightgbm_residual", lightgbm_residual),
        ("interpretable_gam", interpretable_gam),
        ("hierarchical_rate_model", hierarchical_rate_model),
    ]

    all_metrics: list[dict] = []
    all_market_metrics: list[pd.DataFrame] = []
    all_month_metrics: list[pd.DataFrame] = []
    predictions: dict[str, np.ndarray] = {}
    status: list[dict] = []

    for name, runner in runners:
        started = time.perf_counter()
        try:
            prediction = runner(train, test)
            if len(prediction) != len(test) or not np.isfinite(prediction).all():
                raise RuntimeError("Prediction output is incomplete or non-finite")
            predictions[name] = prediction
            scored = test[["date", "segment", "market", "guests", "prior_year_guests"]].copy()
            scored["prediction"] = prediction
            metrics, market_metrics, month_metrics = evaluate_predictions(
                scored, name, mase_scales
            )
            all_metrics.extend(metrics)
            all_market_metrics.append(market_metrics)
            all_month_metrics.append(month_metrics)
            scored.to_csv(OUTPUT / f"predictions__{name}.csv", index=False)
            status.append(
                {"model": name, "status": "ok", "seconds": round(time.perf_counter() - started, 3)}
            )
            print(f"completed {name} in {status[-1]['seconds']:.1f}s", flush=True)
        except Exception as exc:  # preserve all other model results
            status.append(
                {
                    "model": name,
                    "status": "failed",
                    "seconds": round(time.perf_counter() - started, 3),
                    "error": repr(exc),
                }
            )
            print(f"FAILED {name}: {exc!r}", flush=True)

    if "hybrid_residual_xgboost" in predictions and "pooled_catboost" in predictions:
        name = "ensemble_blend"
        prediction = 0.5 * predictions["hybrid_residual_xgboost"] + 0.5 * predictions["pooled_catboost"]
        predictions[name] = prediction
        scored = test[["date", "segment", "market", "guests", "prior_year_guests"]].copy()
        scored["prediction"] = prediction
        metrics, market_metrics, month_metrics = evaluate_predictions(scored, name, mase_scales)
        all_metrics.extend(metrics)
        all_market_metrics.append(market_metrics)
        all_month_metrics.append(month_metrics)
        scored.to_csv(OUTPUT / f"predictions__{name}.csv", index=False)
        status.append({"model": name, "status": "ok", "seconds": 0.0})

    metrics_frame = pd.DataFrame(all_metrics)
    metrics_frame.to_csv(OUTPUT / "offline_metrics_by_scope.csv", index=False)
    if all_market_metrics:
        pd.concat(all_market_metrics, ignore_index=True).to_csv(
            OUTPUT / "offline_metrics_by_market.csv", index=False
        )
    if all_month_metrics:
        pd.concat(all_month_metrics, ignore_index=True).to_csv(
            OUTPUT / "offline_metrics_by_month.csv", index=False
        )
    pd.DataFrame(status).to_csv(OUTPUT / "pipeline_status.csv", index=False)

    combined = metrics_frame[metrics_frame["scope"].eq("combined")].sort_values("wmape")
    combined.to_csv(OUTPUT / "leaderboard_combined.csv", index=False)
    print("\nCOMBINED OFFLINE LEADERBOARD")
    print(
        combined[
            [
                "model",
                "wmape",
                "bias_pct",
                "mae",
                "rmse",
                "mase",
                "relative_mae_vs_seasonal_naive",
                "r2",
            ]
        ].to_string(
            index=False, float_format=lambda x: f"{x:.6f}"
        )
    )


if __name__ == "__main__":
    main()
