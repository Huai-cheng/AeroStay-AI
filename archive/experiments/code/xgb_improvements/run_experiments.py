"""Focused improvements for the pooled international Demand XGBoost model."""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipelines" / "common"))
import run_offline_benchmark as common  # noqa: E402


OUTPUT = ROOT / "artifacts" / "xgb_improvements"
TUNE_END = pd.Timestamp("2024-01-31")
VALIDATION_START = pd.Timestamp("2024-02-01")
VALIDATION_END = pd.Timestamp("2024-07-31")
RANDOM_STATE = 20261010
EPS = 1e-9

# Remove duplicated raw month/day numbers and constant segment.  Cyclical time,
# explicit categories, demand, and historical references remain.
NUMERIC = [
    "trend_days",
    "day_of_year_sin",
    "day_of_year_cos",
    "is_weekend",
    "new_arrivals",
    "same_day_guests",
    "same_day_missing",
    "prior_year_guests",
    "prior_year_arrivals",
    "arrivals_yoy_ratio",
]
CATEGORICAL = ["market", "month_cat", "dow_cat"]
FEATURES = NUMERIC + CATEGORICAL


def wmape(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.abs(actual - predicted).sum() / max(np.abs(actual).sum(), EPS))


def xgb_wmape(actual: np.ndarray, predicted: np.ndarray) -> float:
    return wmape(np.asarray(actual), np.asarray(predicted))


def log_wmape(actual_log: np.ndarray, predicted_log: np.ndarray) -> float:
    actual = np.expm1(np.asarray(actual_log))
    predicted = np.clip(np.expm1(np.asarray(predicted_log)), 0.0, None)
    return wmape(actual, predicted)


def preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        [("impute", SimpleImputer(strategy="median", add_indicator=True))]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [("numeric", numeric, NUMERIC), ("category", categorical, CATEGORICAL)]
    )


def base_params(**overrides) -> dict:
    params = {
        "objective": "reg:squarederror",
        "n_estimators": 3000,
        "learning_rate": 0.03,
        "max_depth": 4,
        "min_child_weight": 15,
        "gamma": 0.0,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_lambda": 10.0,
        "reg_alpha": 0.1,
        "tree_method": "hist",
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
        "early_stopping_rounds": 100,
        "eval_metric": xgb_wmape,
    }
    params.update(overrides)
    return params


def transform_for_fit(
    train: pd.DataFrame, validation: pd.DataFrame, final_train: pd.DataFrame, test: pd.DataFrame
):
    tune_transformer = preprocessor()
    x_train = tune_transformer.fit_transform(train[FEATURES])
    x_validation = tune_transformer.transform(validation[FEATURES])

    final_transformer = preprocessor()
    x_final = final_transformer.fit_transform(final_train[FEATURES])
    x_test = final_transformer.transform(test[FEATURES])
    return tune_transformer, x_train, x_validation, final_transformer, x_final, x_test


def fit_transformed_variant(
    name: str,
    params: dict,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    final_train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    target_mode: str = "direct",
    monotonic: bool = False,
) -> tuple[np.ndarray, dict]:
    fit_train = train.copy()
    fit_validation = validation.copy()
    fit_final = final_train.copy()

    if target_mode == "residual":
        fit_train = fit_train[fit_train["prior_year_guests"].notna()].copy()
        fit_validation = fit_validation[fit_validation["prior_year_guests"].notna()].copy()
        fit_final = fit_final[fit_final["prior_year_guests"].notna()].copy()

    tune_transformer, x_train, x_validation, _, x_final, x_test = transform_for_fit(
        fit_train, fit_validation, fit_final, test
    )

    y_train = fit_train["guests"].to_numpy()
    y_validation = fit_validation["guests"].to_numpy()
    y_final = fit_final["guests"].to_numpy()
    metric = xgb_wmape

    if target_mode == "log1p":
        y_train = np.log1p(y_train)
        y_validation = np.log1p(y_validation)
        y_final = np.log1p(y_final)
        metric = log_wmape
    elif target_mode == "residual":
        y_train = y_train - fit_train["prior_year_guests"].to_numpy()
        y_validation = y_validation - fit_validation["prior_year_guests"].to_numpy()
        y_final = y_final - fit_final["prior_year_guests"].to_numpy()
        metric = "mae"

    tune_params = dict(params)
    tune_params["eval_metric"] = metric

    if monotonic:
        transformed_names = list(tune_transformer.get_feature_names_out())
        constraints = [0] * len(transformed_names)
        constraints[transformed_names.index("numeric__new_arrivals")] = 1
        tune_params["monotone_constraints"] = tuple(constraints)
        tune_params["max_bin"] = 512

    tune_model = XGBRegressor(**tune_params)
    tune_model.fit(
        x_train,
        y_train,
        eval_set=[(x_validation, y_validation)],
        verbose=False,
    )
    best_trees = int(tune_model.best_iteration) + 1

    final_params = dict(tune_params)
    final_params.pop("early_stopping_rounds", None)
    final_params["n_estimators"] = best_trees
    final_model = XGBRegressor(**final_params)
    final_model.fit(x_final, y_final, verbose=False)
    prediction = final_model.predict(x_test)

    if target_mode == "log1p":
        prediction = np.expm1(prediction)
    elif target_mode == "residual":
        prediction = test["prior_year_guests"].to_numpy() + prediction

    prediction = np.clip(prediction, 0.0, None)
    metadata = {
        "model": name,
        "best_trees": best_trees,
        "validation_best_score": float(tune_model.best_score),
        "objective": str(params.get("objective")),
        "target_mode": target_mode,
    }
    return prediction, metadata


def categorical_frames(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    final_train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    def prepare(source: pd.DataFrame, category_levels: dict[str, list]) -> pd.DataFrame:
        result = source[FEATURES].copy()
        for col in CATEGORICAL:
            result[col] = pd.Categorical(result[col].astype(str), categories=category_levels[col])
        return result

    tune_levels = {
        col: sorted(train[col].dropna().astype(str).unique().tolist()) for col in CATEGORICAL
    }
    final_levels = {
        col: sorted(final_train[col].dropna().astype(str).unique().tolist()) for col in CATEGORICAL
    }
    return (
        prepare(train, tune_levels),
        prepare(validation, tune_levels),
        prepare(final_train, final_levels),
        prepare(test, final_levels),
    )


def fit_native_categorical(
    params: dict,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    final_train: pd.DataFrame,
    test: pd.DataFrame,
) -> tuple[np.ndarray, dict]:
    x_train, x_validation, x_final, x_test = categorical_frames(
        train, validation, final_train, test
    )
    tune_params = dict(params)
    tune_params.update({"enable_categorical": True, "max_cat_to_onehot": 8})
    tune_model = XGBRegressor(**tune_params)
    tune_model.fit(
        x_train,
        train["guests"],
        eval_set=[(x_validation, validation["guests"])],
        verbose=False,
    )
    best_trees = int(tune_model.best_iteration) + 1
    final_params = dict(tune_params)
    final_params.pop("early_stopping_rounds", None)
    final_params["n_estimators"] = best_trees
    final_model = XGBRegressor(**final_params)
    final_model.fit(x_final, final_train["guests"], verbose=False)
    prediction = np.clip(final_model.predict(x_test), 0.0, None)
    return prediction, {
        "model": "xgb_native_categorical",
        "best_trees": best_trees,
        "validation_best_score": float(tune_model.best_score),
        "objective": str(params.get("objective")),
        "target_mode": "direct",
    }


def score(test: pd.DataFrame, prediction: np.ndarray, name: str) -> dict:
    actual = test["guests"].to_numpy()
    error = prediction - actual
    market_wmapes = []
    scored = test[["date", "market", "guests"]].copy()
    scored["prediction"] = prediction
    for _, part in scored.groupby("market", observed=True):
        market_wmapes.append(wmape(part["guests"].to_numpy(), part["prediction"].to_numpy()))
    return {
        "model": name,
        "wmape": wmape(actual, prediction),
        "bias_pct": float(error.sum() / actual.sum()),
        "mae": float(np.abs(error).mean()),
        "rmse": float(math.sqrt(np.mean(error**2))),
        "macro_market_wmape": float(np.mean(market_wmapes)),
        "median_market_wmape": float(np.median(market_wmapes)),
        "p90_market_wmape": float(np.quantile(market_wmapes, 0.90)),
        "actual_total": float(actual.sum()),
        "predicted_total": float(prediction.sum()),
    }


def tune_square_structure(
    train: pd.DataFrame,
    validation: pd.DataFrame,
) -> tuple[dict, pd.DataFrame]:
    transformer = preprocessor()
    x_train = transformer.fit_transform(train[FEATURES])
    x_validation = transformer.transform(validation[FEATURES])
    candidates = [
        {"max_depth": 3, "min_child_weight": 10, "learning_rate": 0.03},
        {"max_depth": 4, "min_child_weight": 10, "learning_rate": 0.03},
        {"max_depth": 5, "min_child_weight": 15, "learning_rate": 0.03},
        {"max_depth": 4, "min_child_weight": 25, "learning_rate": 0.02},
        {"max_depth": 5, "min_child_weight": 25, "learning_rate": 0.02},
        {"max_depth": 6, "min_child_weight": 30, "learning_rate": 0.02},
    ]
    records = []
    for candidate in candidates:
        params = base_params(**candidate)
        model = XGBRegressor(**params)
        model.fit(
            x_train,
            train["guests"],
            eval_set=[(x_validation, validation["guests"])],
            verbose=False,
        )
        records.append(
            {
                **candidate,
                "best_trees": int(model.best_iteration) + 1,
                "validation_wmape": float(model.best_score),
            }
        )
        print(f"tuned candidate {candidate}: {model.best_score:.6f}", flush=True)
    results = pd.DataFrame(records).sort_values("validation_wmape")
    best = results.iloc[0]
    best_params = base_params(
        max_depth=int(best["max_depth"]),
        min_child_weight=float(best["min_child_weight"]),
        learning_rate=float(best["learning_rate"]),
    )
    return best_params, results


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hotel = common.load_hotel_data()
    flight_global, flight_market = common.load_flight_features()
    data = common.add_features(hotel, flight_global, flight_market)
    train_all, test_all = common.split_data(data)
    final_train = train_all[train_all["segment"].eq("International")].copy()
    test = test_all[test_all["segment"].eq("International")].copy()
    train = final_train[final_train["date"] <= TUNE_END].copy()
    validation = final_train[
        (final_train["date"] >= VALIDATION_START)
        & (final_train["date"] <= VALIDATION_END)
    ].copy()

    tuned_params, search_results = tune_square_structure(train, validation)
    search_results.to_csv(OUTPUT / "hyperparameter_search.csv", index=False)

    variants = [
        (
            "xgb_clean_earlystop",
            base_params(max_depth=5, min_child_weight=15, learning_rate=0.035),
            "direct",
            False,
        ),
        ("xgb_tuned_square", tuned_params, "direct", False),
        (
            "xgb_log1p",
            {**tuned_params, "objective": "reg:squarederror"},
            "log1p",
            False,
        ),
        (
            "xgb_poisson",
            {**tuned_params, "objective": "count:poisson", "max_delta_step": 0.7},
            "direct",
            False,
        ),
        (
            "xgb_pseudohuber",
            {**tuned_params, "objective": "reg:pseudohubererror"},
            "direct",
            False,
        ),
        ("xgb_prior_year_residual", tuned_params, "residual", False),
        ("xgb_monotonic_arrivals", tuned_params, "direct", True),
    ]

    leaderboard = []
    metadata = []
    for name, params, target_mode, monotonic in variants:
        started = time.perf_counter()
        try:
            prediction, details = fit_transformed_variant(
                name,
                params,
                train,
                validation,
                final_train,
                test,
                target_mode=target_mode,
                monotonic=monotonic,
            )
            details["seconds"] = round(time.perf_counter() - started, 3)
            details["status"] = "ok"
            metadata.append(details)
            leaderboard.append(score(test, prediction, name))
            output = test[["date", "market", "guests"]].copy()
            output["prediction"] = prediction
            output.to_csv(OUTPUT / f"predictions__{name}.csv", index=False)
            print(f"completed {name}: {leaderboard[-1]['wmape']:.6f}", flush=True)
        except Exception as exc:
            metadata.append(
                {
                    "model": name,
                    "status": "failed",
                    "error": repr(exc),
                    "seconds": round(time.perf_counter() - started, 3),
                }
            )
            print(f"FAILED {name}: {exc!r}", flush=True)

    started = time.perf_counter()
    try:
        prediction, details = fit_native_categorical(
            tuned_params, train, validation, final_train, test
        )
        details["seconds"] = round(time.perf_counter() - started, 3)
        details["status"] = "ok"
        metadata.append(details)
        leaderboard.append(score(test, prediction, "xgb_native_categorical"))
        output = test[["date", "market", "guests"]].copy()
        output["prediction"] = prediction
        output.to_csv(OUTPUT / "predictions__xgb_native_categorical.csv", index=False)
        print(f"completed xgb_native_categorical: {leaderboard[-1]['wmape']:.6f}", flush=True)
    except Exception as exc:
        metadata.append(
            {
                "model": "xgb_native_categorical",
                "status": "failed",
                "error": repr(exc),
                "seconds": round(time.perf_counter() - started, 3),
            }
        )
        print(f"FAILED xgb_native_categorical: {exc!r}", flush=True)

    existing = ROOT / "artifacts" / "offline_metrics" / "predictions__demand_xgboost.csv"
    if existing.exists():
        baseline = pd.read_csv(existing)
        baseline = baseline[baseline["segment"].eq("International")]
        leaderboard.append(
            score(test, baseline["prediction"].to_numpy(), "existing_demand_xgboost")
        )

    leaderboard_frame = pd.DataFrame(leaderboard).sort_values("wmape")
    leaderboard_frame.to_csv(OUTPUT / "leaderboard.csv", index=False)
    pd.DataFrame(metadata).to_csv(OUTPUT / "pipeline_status.csv", index=False)
    run_metadata = {
        "tuning_train_end": str(TUNE_END.date()),
        "validation_start": str(VALIDATION_START.date()),
        "validation_end": str(VALIDATION_END.date()),
        "offline_test_start": str(common.TEST_START.date()),
        "offline_test_end": str(common.TEST_END.date()),
        "raw_features": FEATURES,
        "selected_tuning_parameters": {
            key: value
            for key, value in tuned_params.items()
            if key
            in {
                "max_depth",
                "min_child_weight",
                "learning_rate",
                "subsample",
                "colsample_bytree",
                "reg_lambda",
                "reg_alpha",
            }
        },
    }
    (OUTPUT / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2), encoding="utf-8"
    )
    print("\nXGBOOST IMPROVEMENT LEADERBOARD")
    print(
        leaderboard_frame[
            [
                "model",
                "wmape",
                "bias_pct",
                "mae",
                "rmse",
                "macro_market_wmape",
                "p90_market_wmape",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.6f}")
    )


if __name__ == "__main__":
    main()

