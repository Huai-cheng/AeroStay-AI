"""Back-test and refit the selected pooled Poisson XGBoost approach."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from pipeline.modeling import (
    ARTIFACT_DIR,
    build_features,
    fit_pooled_model,
    load_hotel_data,
    predict_with_model,
    save_model,
)


HOLDOUT_START = pd.Timestamp("2024-08-01")
HOLDOUT_END = pd.Timestamp("2025-02-28")

CANONICAL_FEATURES = Path(__file__).resolve().parents[1] / "artifacts" / "etl" / "hotel_daily.csv"
CANONICAL_RENAMES = {
    "linear_time_trend_days": "trend_days",
    "annual_seasonal_sine": "day_of_year_sin",
    "annual_seasonal_cosine": "day_of_year_cos",
    "weekend_indicator": "is_weekend",
    "same_day_guests_missing_indicator": "same_day_missing",
    "previous_year_total_guests": "prior_year_guests",
    "previous_year_new_arrivals": "prior_year_arrivals",
    "year_over_year_arrival_ratio": "arrivals_yoy_ratio",
    "month_category": "month_cat",
    "day_of_week_category": "dow_cat",
}


def load_canonical_training_features() -> pd.DataFrame:
    """Load the exact ETL representation used for model selection."""
    if not CANONICAL_FEATURES.exists():
        from etl.build_feature_tables import main as build_feature_tables

        build_feature_tables()
    frame = pd.read_csv(CANONICAL_FEATURES, parse_dates=["date"])
    return frame.rename(columns=CANONICAL_RENAMES)


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    error = predicted - actual
    return {
        "rows": int(len(actual)),
        "wmape": float(np.abs(error).sum() / actual.sum()),
        "bias_pct": float(error.sum() / actual.sum()),
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "actual_total": float(actual.sum()),
        "predicted_total": float(predicted.sum()),
    }


def main() -> None:
    train_raw, official_test_raw = load_hotel_data()
    origin_date = train_raw["date"].min()
    canonical_features = load_canonical_training_features()

    train_features = canonical_features[canonical_features["date"] < HOLDOUT_START].copy()
    test_features = canonical_features[
        canonical_features["date"].between(HOLDOUT_START, HOLDOUT_END)
    ].copy()
    holdout_model = fit_pooled_model(train_features)
    holdout_prediction = predict_with_model(holdout_model, test_features)
    scored = test_features[["date", "segment", "market", "guests"]].copy()
    scored["prediction"] = holdout_prediction

    results = {}
    for scope, mask in {
        "combined": np.ones(len(scored), dtype=bool),
        "domestic": scored["segment"].eq("Domestic").to_numpy(),
        "international": scored["segment"].eq("International").to_numpy(),
    }.items():
        results[scope] = metrics(
            scored.loc[mask, "guests"].to_numpy(),
            scored.loc[mask, "prediction"].to_numpy(),
        )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    scored.to_csv(ARTIFACT_DIR / "holdout_predictions.csv", index=False)
    (ARTIFACT_DIR / "holdout_metrics.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    full_train_features = canonical_features.copy()
    official_test_features = build_features(
        official_test_raw, train_raw, origin_date=origin_date
    )
    final_model = fit_pooled_model(full_train_features)
    baseline_prediction = predict_with_model(final_model, official_test_features)
    baseline = official_test_features[
        [
            "date",
            "segment",
            "market",
            "new_arrivals",
            "same_day_guests",
            "same_day_missing",
            "prior_year_guests",
            "prior_year_arrivals",
        ]
    ].copy()
    baseline["predicted_guests"] = baseline_prediction
    baseline["predicted_guest_nights"] = np.clip(
        baseline["predicted_guests"] - baseline["same_day_guests"].fillna(0),
        0.0,
        None,
    )
    baseline.to_csv(ARTIFACT_DIR / "official_test_baseline.csv", index=False)

    metadata = {
        "approach": "Pooled Poisson XGBoost",
        "objective": "count:poisson",
        "feature_definition": "B0 current baseline",
        "feature_count_before_encoding": 14,
        "target": "Guests",
        "guest_night_derivation": "predicted Guests - Same-Day Guests",
        "train_start": str(train_raw["date"].min().date()),
        "train_end": str(train_raw["date"].max().date()),
        "official_test_start": str(official_test_raw["date"].min().date()),
        "official_test_end": str(official_test_raw["date"].max().date()),
        "models": ["One pooled Domestic + International estimator"],
        "holdout_metrics": results,
    }
    save_model(final_model, metadata)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
