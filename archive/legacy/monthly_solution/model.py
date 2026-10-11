"""Time-ordered model selection, back-testing, and serving bundles."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
import yaml
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from dtc.config import processed_path, raw_path
from dtc.data import build_features, map_markets, prepare, write_audit, write_split


CATEGORICAL = ["nationality"]
NUMERIC = [
    "month_number", "year_index", "direct_origin_seats", "allocated_origin_seats", "citywide_seats",
    "arrivals_same_month_last_year", "allocated_seats_same_month_last_year", "lag12_missing",
]
FEATURE_COLUMNS = CATEGORICAL + NUMERIC


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("market", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("numbers", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value=0)),
                                   ("scale", StandardScaler())]), NUMERIC),
        ],
        remainder="drop",
    )


def _estimator(name: str, seed: int) -> TransformedTargetRegressor:
    if name == "regression":
        estimator = Ridge(alpha=20.0)
    elif name == "xgboost":
        estimator = XGBRegressor(
            n_estimators=240, max_depth=3, learning_rate=0.045,
            min_child_weight=8, subsample=0.85, colsample_bytree=0.85,
            reg_lambda=10, objective="reg:squarederror", random_state=seed,
            n_jobs=2,
        )
    else:
        raise ValueError(f"Unknown model: {name}")
    return TransformedTargetRegressor(
        regressor=Pipeline([("prepare", _preprocessor()), ("fit", estimator)]),
        func=np.log1p, inverse_func=np.expm1, check_inverse=False,
    )


def _predict(model: Any, frame: pd.DataFrame) -> np.ndarray:
    return np.maximum(0, np.asarray(model.predict(frame[FEATURE_COLUMNS]), dtype=float))


def _seasonal(frame: pd.DataFrame, fallback: dict[str, float]) -> np.ndarray:
    lag = frame["arrivals_same_month_last_year"].to_numpy(dtype=float)
    markets = frame["nationality"].astype(str).to_list()
    return np.array([max(0, value) if np.isfinite(value) else fallback.get(market, fallback["__global__"])
                     for value, market in zip(lag, markets)], dtype=float)


def _fallback(train: pd.DataFrame) -> dict[str, float]:
    observed = train.groupby("nationality")["hotel_new_arrivals"].median().dropna().to_dict()
    observed["__global__"] = float(train["hotel_new_arrivals"].median())
    return {str(k): float(v) for k, v in observed.items()}


def _seasonal_air(frame: pd.DataFrame, fallback: dict[str, float], elasticity: float,
                  config: dict[str, Any]) -> np.ndarray:
    baseline = _seasonal(frame, fallback)
    current = frame["allocated_origin_seats"].to_numpy(dtype=float)
    prior = frame["allocated_seats_same_month_last_year"].to_numpy(dtype=float)
    smoothing = float(config["model"]["seat_smoothing"])
    lower, upper = (float(x) for x in config["model"]["capacity_ratio_clip"])
    ratio = np.ones(len(frame), dtype=float)
    known = np.isfinite(prior) & np.isfinite(current)
    ratio[known] = np.clip((current[known] + smoothing) / (prior[known] + smoothing), lower, upper)
    return baseline * ratio ** elasticity


def metrics(actual: np.ndarray | pd.Series, predicted: np.ndarray | pd.Series) -> dict[str, float]:
    y = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    mask = np.isfinite(y) & np.isfinite(p)
    y, p = y[mask], p[mask]
    if not len(y):
        raise ValueError("No labelled rows available for evaluation")
    abs_error = np.abs(y - p)
    denom = np.abs(y).sum()
    return {
        "rows": int(len(y)),
        "wmape_percent": float(100 * abs_error.sum() / denom) if denom else None,
        "mae": float(abs_error.mean()),
        "bias_percent": float(100 * (p - y).sum() / denom) if denom else None,
    }


def _load_features(config: dict[str, Any]) -> pd.DataFrame:
    return pd.read_csv(processed_path(config, "market_month_features.csv"), parse_dates=["month"])


def _reference(config: dict[str, Any], hotel: pd.DataFrame, air: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, Any]:
    history = hotel.loc[hotel["split"].eq("train") & hotel["month"].le(end_date)].copy()
    year_ago = end_date - pd.DateOffset(years=1)
    recent = history.loc[history["month"].gt(year_ago)]
    air_recent = air.loc[air["month"].gt(year_ago) & air["month"].le(end_date)].copy()
    p2p = float(air_recent["p2p"].sum())
    total_arrivals = float(recent["hotel_new_arrivals"].sum())
    effective = total_arrivals / p2p if p2p else 0.0
    monthly_air = air_recent.groupby("month")["p2p"].sum()
    monthly_hotel = recent.groupby("month")["hotel_new_arrivals"].sum()
    monthly_ratio = (monthly_hotel / monthly_air.replace(0, np.nan)).dropna()
    conversion_low = float(monthly_ratio.quantile(0.10)) if len(monthly_ratio) else effective
    conversion_high = float(monthly_ratio.quantile(0.90)) if len(monthly_ratio) else effective
    visitor_share = float(config["assumptions"]["nonresident_visitor_share"])
    if effective > visitor_share:
        raise ValueError("Observed hotel/P2P ratio exceeds visitor-share assumption; revise assumptions")
    stay_rows = history.loc[history["missing_new_arrivals"].eq(0) & history["hotel_new_arrivals"].gt(0)]
    global_stay = float(stay_rows["guest_days"].sum() / stay_rows["hotel_new_arrivals"].sum())
    stay_by_market = stay_rows.groupby("nationality").apply(
        lambda g: float(g["guest_days"].sum() / g["hotel_new_arrivals"].sum()),
        include_groups=False,
    ).to_dict()
    shares = recent.groupby("nationality")["hotel_new_arrivals"].sum()
    shares = (shares / shares.sum()).to_dict()
    air_rates = air_recent.groupby("departure_country")[
        ["seats", "passengers", "transfers", "transit"]
    ].sum()
    origin_rates = {}
    for origin, row in air_rates.iterrows():
        pax = float(row["passengers"])
        origin_rates[str(origin)] = {
            "load_factor": float(pax / row["seats"]) if row["seats"] else 0.0,
            "transfer_transit_share": float((row["transfers"] + row["transit"]) / pax) if pax else 0.0,
        }
    total_seats = float(air_recent["seats"].sum())
    total_pax = float(air_recent["passengers"].sum())
    return {
        "calibration_end": end_date.date().isoformat(),
        "effective_hotel_conversion_from_p2p": effective,
        "effective_conversion_monthly_p10_p90": [conversion_low, conversion_high],
        "nonresident_visitor_share_assumed": visitor_share,
        "hotel_capture_rate_derived": effective / visitor_share,
        "stay_proxy_global": global_stay,
        "stay_proxy_by_nationality": {str(k): float(v) for k, v in stay_by_market.items()},
        "hotel_nationality_shares": {str(k): float(v) for k, v in shares.items()},
        "origin_rates": origin_rates,
        "pooled_origin_rates": {
            "load_factor": total_pax / total_seats,
            "transfer_transit_share": float((air_recent["transfers"].sum() + air_recent["transit"].sum()) / total_pax),
        },
        "same_origin_nationality_share_assumed": float(config["assumptions"]["same_origin_nationality_share"]),
        "rate_note": "Visitor share and nationality allocation are unobserved assumptions; capture is calibrated to aggregate hotel arrivals/P2P.",
    }


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _code_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        digest.update(str(path.relative_to(Path(__file__).parent)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def train(config: dict[str, Any]) -> tuple[str, Path]:
    write_audit(config)
    prepare(config)
    map_markets(config)
    build_features(config)
    write_split(config)
    frame = _load_features(config)
    frame = frame.loc[frame["split"].eq("train") & frame["missing_new_arrivals"].eq(0)].copy()
    train_end = pd.Timestamp(config["split"]["train_end"])
    valid_start = pd.Timestamp(config["split"]["validation_start"])
    valid_end = pd.Timestamp(config["split"]["validation_end"])
    development = frame.loc[frame["month"].lt(train_end - pd.DateOffset(years=1) + pd.DateOffset(days=1))]
    selection = frame.loc[frame["month"].gt(development["month"].max()) & frame["month"].le(train_end)]
    final_train = frame.loc[frame["month"].le(train_end)]
    holdout = frame.loc[frame["month"].ge(valid_start) & frame["month"].le(valid_end)]
    if any(len(x) == 0 for x in (development, selection, final_train, holdout)):
        raise ValueError("Training, selection, or holdout period has no labelled rows")

    seed = int(config["model"]["random_seed"])
    selection_fallback = _fallback(development)
    selection_metrics: dict[str, Any] = {
        "seasonal_naive": metrics(selection["hotel_new_arrivals"], _seasonal(selection, selection_fallback))
    }
    for elasticity in config["model"]["air_elasticity_candidates"]:
        name = f"seasonal_air_e{float(elasticity):g}"
        selection_metrics[name] = metrics(
            selection["hotel_new_arrivals"],
            _seasonal_air(selection, selection_fallback, float(elasticity), config),
        )
    for name in ("regression", "xgboost"):
        candidate = _estimator(name, seed)
        candidate.fit(development[FEATURE_COLUMNS], development["hotel_new_arrivals"].to_numpy())
        selection_metrics[name] = metrics(selection["hotel_new_arrivals"], _predict(candidate, selection))
    chosen = min(selection_metrics, key=lambda name: selection_metrics[name]["wmape_percent"])

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]
    run_dir = Path(config["artifacts"]["runs_dir"]) / run_id
    for child in ("model", "metrics", "predictions", "reports"):
        (run_dir / child).mkdir(parents=True, exist_ok=True)
    for name in ("data_quality.json", "split_manifest.json", "market_allocation_assumption.csv"):
        shutil.copyfile(processed_path(config, name), run_dir / "reports" / name)

    if chosen in ("regression", "xgboost"):
        backtest_model = _estimator(chosen, seed)
        backtest_model.fit(final_train[FEATURE_COLUMNS], final_train["hotel_new_arrivals"].to_numpy())
        joblib.dump(backtest_model, run_dir / "model" / "backtest.joblib")
        serving_model = _estimator(chosen, seed)
        serving_model.fit(frame[FEATURE_COLUMNS], frame["hotel_new_arrivals"].to_numpy())
        joblib.dump(serving_model, run_dir / "model" / "serving.joblib")
    fallback = _fallback(final_train)
    (run_dir / "model" / "fallback.json").write_text(json.dumps(fallback, indent=2), encoding="utf-8")
    full_fallback = _fallback(frame)
    (run_dir / "model" / "serving_fallback.json").write_text(json.dumps(full_fallback, indent=2), encoding="utf-8")

    hotel = pd.read_csv(processed_path(config, "hotel_nationality_month.csv"), parse_dates=["month"])
    air = pd.read_csv(processed_path(config, "air_origin_month.csv"), parse_dates=["month"])
    references = {
        "backtest": _reference(config, hotel, air, train_end),
        "serving": _reference(config, hotel, air, valid_end),
    }
    (run_dir / "model" / "reference.json").write_text(json.dumps(references, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "selection.json").write_text(json.dumps(selection_metrics, indent=2), encoding="utf-8")
    resolved = {k: v for k, v in config.items() if not k.startswith("_")}
    (run_dir / "config.resolved.yaml").write_text(yaml.safe_dump(resolved, sort_keys=False), encoding="utf-8")
    manifest = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selected_model": chosen,
        "selected_air_elasticity": float(chosen.split("_e")[-1]) if chosen.startswith("seasonal_air_e") else None,
        "code_sha256": _code_hash(),
        "selection_period": [str(selection["month"].min().date()), str(selection["month"].max().date())],
        "holdout_period": [valid_start.date().isoformat(), valid_end.date().isoformat()],
        "backtest_train_end": train_end.date().isoformat(),
        "serving_train_end": str(frame["month"].max().date()),
        "feature_columns": FEATURE_COLUMNS,
        "python_libraries": {"sklearn": sklearn.__version__, "xgboost": xgboost.__version__, "pandas": pd.__version__},
        "input_hashes": {
            key: _hash(raw_path(config, key)) for key in
            ("flight_file", "international_train_file", "international_test_file", "domestic_train_file", "domestic_test_file", "dictionary_file")
        },
        "evaluation_complete": False,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_id, run_dir


def evaluate(config: dict[str, Any], run_id: str) -> dict[str, Any]:
    run_dir = Path(config["artifacts"]["runs_dir"]) / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Unknown run ID: {run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frame = _load_features(config)
    valid_start = pd.Timestamp(manifest["holdout_period"][0])
    valid_end = pd.Timestamp(manifest["holdout_period"][1])
    holdout = frame.loc[frame["split"].eq("train") & frame["month"].between(valid_start, valid_end)
                        & frame["missing_new_arrivals"].eq(0)].copy()
    train_end = pd.Timestamp(manifest["backtest_train_end"])
    fallback = json.loads((run_dir / "model" / "fallback.json").read_text(encoding="utf-8"))
    seasonal_prediction = _seasonal(holdout, fallback)
    if manifest["selected_model"] == "seasonal_naive":
        prediction = seasonal_prediction
    elif manifest["selected_model"].startswith("seasonal_air_e"):
        prediction = _seasonal_air(holdout, fallback, manifest["selected_air_elasticity"], config)
    else:
        predictor = joblib.load(run_dir / "model" / "backtest.joblib")
        prediction = _predict(predictor, holdout)
    reference = json.loads((run_dir / "model" / "reference.json").read_text(encoding="utf-8"))["backtest"]
    stay = reference["stay_proxy_by_nationality"]
    stay_values = holdout["nationality"].map(stay).fillna(reference["stay_proxy_global"]).to_numpy()
    holdout["predicted_arrivals"] = prediction
    holdout["seasonal_arrivals"] = seasonal_prediction
    holdout["predicted_guest_days"] = prediction * stay_values
    holdout["seasonal_guest_days"] = seasonal_prediction * stay_values
    holdout["arrivals_error"] = holdout["predicted_arrivals"] - holdout["hotel_new_arrivals"]
    holdout["guest_days_error"] = holdout["predicted_guest_days"] - holdout["guest_days"]
    summary = {
        "run_id": run_id,
        "model": manifest["selected_model"],
        "holdout": manifest["holdout_period"],
        "arrivals": metrics(holdout["hotel_new_arrivals"], prediction),
        "arrivals_seasonal_baseline": metrics(holdout["hotel_new_arrivals"], seasonal_prediction),
        "guest_days_proxy": metrics(holdout["guest_days"], holdout["predicted_guest_days"]),
        "guest_days_seasonal_baseline": metrics(holdout["guest_days"], holdout["seasonal_guest_days"]),
        "note": "Guest-days are sum of daily Guests, not verified overnight guest nights. Scenario impacts are not causally validated by this back-test.",
    }
    holdout.to_csv(run_dir / "predictions" / "holdout.csv", index=False)
    holdout["absolute_arrivals_error"] = holdout["arrivals_error"].abs()
    holdout["absolute_guest_days_error"] = holdout["guest_days_error"].abs()
    report_columns = ["hotel_new_arrivals", "predicted_arrivals", "guest_days", "predicted_guest_days",
                      "absolute_arrivals_error", "absolute_guest_days_error"]
    by_month = holdout.groupby("month")[report_columns].sum().reset_index()
    by_month["arrivals_wmape_percent"] = 100 * by_month["absolute_arrivals_error"] / by_month["hotel_new_arrivals"].replace(0, np.nan)
    by_month["guest_days_wmape_percent"] = 100 * by_month["absolute_guest_days_error"] / by_month["guest_days"].replace(0, np.nan)
    by_month.to_csv(run_dir / "metrics" / "by_month.csv", index=False)
    by_market = holdout.groupby("nationality")[report_columns].sum().reset_index()
    by_market["arrivals_wmape_percent"] = 100 * by_market["absolute_arrivals_error"] / by_market["hotel_new_arrivals"].replace(0, np.nan)
    by_market["guest_days_wmape_percent"] = 100 * by_market["absolute_guest_days_error"] / by_market["guest_days"].replace(0, np.nan)
    by_market.to_csv(run_dir / "metrics" / "by_market.csv", index=False)
    (run_dir / "metrics" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest["evaluation_complete"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def package(config: dict[str, Any], run_id: str) -> Path:
    run_dir = Path(config["artifacts"]["runs_dir"]) / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Unknown run ID: {run_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("evaluation_complete"):
        raise ValueError("Evaluate the run before packaging it")
    selected = Path(config["artifacts"]["selected_model_file"])
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text(json.dumps({"run_id": run_id}, indent=2), encoding="utf-8")
    return selected


def serving_run_dir(config: dict[str, Any], run_id: str | None = None) -> Path:
    if run_id is None:
        selected = Path(config["artifacts"]["selected_model_file"])
        if not selected.is_file():
            raise FileNotFoundError("No evaluated model selected. Run train and evaluate first.")
        run_id = json.loads(selected.read_text(encoding="utf-8"))["run_id"]
    run_dir = Path(config["artifacts"]["runs_dir"]) / run_id
    if not (run_dir / "manifest.json").is_file():
        raise FileNotFoundError(f"Model run not found: {run_id}")
    return run_dir


def load_serving_bundle(config: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    run_dir = serving_run_dir(config, run_id)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["evaluation_complete"]:
        raise ValueError("Model run has not been evaluated")
    model = None
    if manifest["selected_model"] in ("regression", "xgboost"):
        model = joblib.load(run_dir / "model" / "serving.joblib")
    reference = json.loads((run_dir / "model" / "reference.json").read_text(encoding="utf-8"))["serving"]
    fallback = json.loads((run_dir / "model" / "serving_fallback.json").read_text(encoding="utf-8"))
    return {"run_dir": run_dir, "manifest": manifest, "model": model, "reference": reference, "fallback": fallback}


def baseline_predictions(config: dict[str, Any], bundle: dict[str, Any], month: str) -> pd.DataFrame:
    frame = _load_features(config)
    chosen_month = pd.Timestamp(month + "-01")
    rows = frame.loc[frame["month"].eq(chosen_month)].copy()
    if rows.empty:
        raise ValueError(f"No flight/hotel market rows available for {month}")
    if bundle["model"] is None:
        if bundle["manifest"]["selected_model"].startswith("seasonal_air_e"):
            rows["predicted_arrivals"] = _seasonal_air(
                rows, bundle["fallback"], bundle["manifest"]["selected_air_elasticity"], config
            )
        else:
            rows["predicted_arrivals"] = _seasonal(rows, bundle["fallback"])
    else:
        rows["predicted_arrivals"] = _predict(bundle["model"], rows)
    stay = bundle["reference"]["stay_proxy_by_nationality"]
    rows["stay_proxy"] = rows["nationality"].map(stay).fillna(bundle["reference"]["stay_proxy_global"])
    rows["predicted_guest_days"] = rows["predicted_arrivals"] * rows["stay_proxy"]
    return rows


def predict_official(config: dict[str, Any], run_id: str | None = None) -> Path:
    """Save monthly forecasts for the unlabelled official period."""
    bundle = load_serving_bundle(config, run_id)
    features = _load_features(config)
    months = sorted(features.loc[features["split"].eq("official_test"), "month"].dt.strftime("%Y-%m").unique())
    if not months:
        raise ValueError("No official test months found")
    parts = []
    for month in months:
        rows = baseline_predictions(config, bundle, month)
        rows = rows.loc[rows["split"].eq("official_test"),
                        ["month", "nationality", "predicted_arrivals", "predicted_guest_days"]]
        parts.append(rows)
    output = pd.concat(parts, ignore_index=True)
    output["model_run_id"] = bundle["manifest"]["run_id"]
    path = bundle["run_dir"] / "predictions" / "official_monthly.csv"
    output.to_csv(path, index=False)
    return path
