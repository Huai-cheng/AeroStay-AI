"""Production B0 pooled Poisson XGBoost and its feature preparation.

This is the repository's only serving model. Historical challengers and feature
search code live under ``archive/experiments``.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts" / "selected_model"
RANDOM_STATE = 20261010

NUMERIC_FEATURES = [
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

# Keep the validated B0 column order: column subsampling makes feature order part
# of the reproducible XGBoost configuration.
CATEGORICAL_FEATURES = ["market", "month_cat", "dow_cat", "segment"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [
        str(column)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        for column in result.columns
    ]
    return result


def load_hotel_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    domestic_train = normalize_columns(pd.read_excel(DATA_DIR / "data domestic_train.xlsx"))
    domestic_test = normalize_columns(pd.read_excel(DATA_DIR / "data domestic_test.xlsx"))
    international_train = normalize_columns(
        pd.read_excel(DATA_DIR / "data international_train.xlsx")
    )
    international_test = normalize_columns(
        pd.read_excel(DATA_DIR / "data international_test.xlsx")
    )

    domestic_train["segment"] = "Domestic"
    domestic_train["market"] = "DOMESTIC"
    domestic_test["segment"] = "Domestic"
    domestic_test["market"] = "DOMESTIC"

    international_train["segment"] = "International"
    international_train["market"] = (
        international_train["nationality"].astype(str).str.upper().str.strip()
    )
    international_test["segment"] = "International"
    international_test["market"] = (
        international_test["nationality"].astype(str).str.upper().str.strip()
    )

    train_columns = [
        "date",
        "guests",
        "new_arrivals",
        "same_day_guests",
        "segment",
        "market",
    ]
    test_columns = [
        "date",
        "new_arrivals",
        "same_day_guests",
        "segment",
        "market",
    ]
    train = pd.concat(
        [domestic_train[train_columns], international_train[train_columns]],
        ignore_index=True,
    )
    test = pd.concat(
        [domestic_test[test_columns], international_test[test_columns]],
        ignore_index=True,
    )

    for frame in (train, test):
        frame["date"] = pd.to_datetime(frame["date"])
        frame["new_arrivals"] = pd.to_numeric(frame["new_arrivals"], errors="coerce")
        frame["same_day_guests"] = pd.to_numeric(frame["same_day_guests"], errors="coerce")
    train["guests"] = pd.to_numeric(train["guests"], errors="raise")

    train = train.sort_values(["date", "segment", "market"]).reset_index(drop=True)
    test = test.sort_values(["date", "segment", "market"]).reset_index(drop=True)
    return train, test


def build_features(
    frame: pd.DataFrame,
    history: pd.DataFrame,
    *,
    origin_date: pd.Timestamp,
) -> pd.DataFrame:
    result = frame.copy()
    result["same_day_missing"] = result["same_day_guests"].isna().astype("int8")
    result["trend_days"] = (result["date"] - origin_date).dt.days
    result["dow"] = result["date"].dt.dayofweek
    result["month"] = result["date"].dt.month
    result["month_cat"] = result["month"].astype(str)
    result["dow_cat"] = result["dow"].astype(str)
    result["is_weekend"] = result["dow"].isin([5, 6]).astype("int8")
    angle = 2.0 * np.pi * result["date"].dt.dayofyear / 365.25
    result["day_of_year_sin"] = np.sin(angle)
    result["day_of_year_cos"] = np.cos(angle)

    result["prior_date"] = result["date"] - pd.DateOffset(years=1)
    lookup = history[["date", "segment", "market", "guests", "new_arrivals"]].rename(
        columns={
            "date": "prior_date",
            "guests": "prior_year_guests",
            "new_arrivals": "prior_year_arrivals",
        }
    )
    result = result.merge(
        lookup,
        on=["prior_date", "segment", "market"],
        how="left",
        validate="many_to_one",
    )
    result["arrivals_yoy_ratio"] = (
        result["new_arrivals"] / result["prior_year_arrivals"].clip(lower=1.0)
    )
    return result


def make_model() -> Pipeline:
    """Build the selected estimator with the frozen B0 feature definition."""
    numeric_pipeline = Pipeline(
        [
            (
                "impute",
                SimpleImputer(
                    strategy="median",
                    add_indicator=True,
                    keep_empty_features=True,
                ),
            ),
        ]
    )
    category_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    processor = ColumnTransformer(
        [
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("category", category_pipeline, CATEGORICAL_FEATURES),
        ]
    )
    estimator = XGBRegressor(
        objective="count:poisson",
        n_estimators=1080,
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
    return Pipeline([("features", processor), ("model", estimator)])


def fit_pooled_model(train_features: pd.DataFrame) -> Pipeline:
    """Fit one model across both segments; ``segment`` remains an input feature."""
    model = make_model()
    model.fit(train_features[MODEL_FEATURES], train_features["guests"])
    return model


def predict_with_model(model: Pipeline, features: pd.DataFrame) -> np.ndarray:
    prediction = model.predict(features[MODEL_FEATURES])
    return np.clip(np.asarray(prediction, dtype=float), 0.0, None)


def save_model(model: Pipeline, metadata: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT_DIR / "pooled_poisson_xgboost.joblib")
    (ARTIFACT_DIR / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def load_model() -> Pipeline:
    return joblib.load(ARTIFACT_DIR / "pooled_poisson_xgboost.joblib")
