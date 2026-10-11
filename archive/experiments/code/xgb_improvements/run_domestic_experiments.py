"""Run the focused XGBoost improvement batch on the domestic daily series."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipelines" / "common"))
sys.path.insert(0, str(ROOT / "pipelines" / "xgb_improvements"))
import run_offline_benchmark as common  # noqa: E402
import run_experiments as experiment  # noqa: E402


OUTPUT = ROOT / "artifacts" / "xgb_improvements"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hotel = common.load_hotel_data()
    flight_global, flight_market = common.load_flight_features()
    data = common.add_features(hotel, flight_global, flight_market)
    train_all, test_all = common.split_data(data)
    final_train = train_all[train_all["segment"].eq("Domestic")].copy()
    test = test_all[test_all["segment"].eq("Domestic")].copy()
    train = final_train[final_train["date"] <= experiment.TUNE_END].copy()
    validation = final_train[
        (final_train["date"] >= experiment.VALIDATION_START)
        & (final_train["date"] <= experiment.VALIDATION_END)
    ].copy()

    tuned_params, search_results = experiment.tune_square_structure(train, validation)
    search_results.to_csv(OUTPUT / "domestic_hyperparameter_search.csv", index=False)

    variants = [
        (
            "domestic_xgb_clean_earlystop",
            experiment.base_params(max_depth=5, min_child_weight=15, learning_rate=0.035),
            "direct",
            False,
        ),
        ("domestic_xgb_tuned_square", tuned_params, "direct", False),
        ("domestic_xgb_log1p", tuned_params, "log1p", False),
        (
            "domestic_xgb_poisson",
            {**tuned_params, "objective": "count:poisson", "max_delta_step": 0.7},
            "direct",
            False,
        ),
        (
            "domestic_xgb_pseudohuber",
            {**tuned_params, "objective": "reg:pseudohubererror"},
            "direct",
            False,
        ),
        ("domestic_xgb_prior_year_residual", tuned_params, "residual", False),
        ("domestic_xgb_monotonic_arrivals", tuned_params, "direct", True),
    ]

    leaderboard = []
    statuses = []
    for name, params, target_mode, monotonic in variants:
        started = time.perf_counter()
        try:
            prediction, details = experiment.fit_transformed_variant(
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
            statuses.append(details)
            leaderboard.append(experiment.score(test, prediction, name))
            output = test[["date", "market", "guests"]].copy()
            output["prediction"] = prediction
            output.to_csv(OUTPUT / f"predictions__{name}.csv", index=False)
            print(f"completed {name}: {leaderboard[-1]['wmape']:.6f}", flush=True)
        except Exception as exc:
            statuses.append(
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
        prediction, details = experiment.fit_native_categorical(
            tuned_params, train, validation, final_train, test
        )
        name = "domestic_xgb_native_categorical"
        details["model"] = name
        details["seconds"] = round(time.perf_counter() - started, 3)
        details["status"] = "ok"
        statuses.append(details)
        leaderboard.append(experiment.score(test, prediction, name))
        output = test[["date", "market", "guests"]].copy()
        output["prediction"] = prediction
        output.to_csv(OUTPUT / f"predictions__{name}.csv", index=False)
        print(f"completed {name}: {leaderboard[-1]['wmape']:.6f}", flush=True)
    except Exception as exc:
        statuses.append(
            {
                "model": "domestic_xgb_native_categorical",
                "status": "failed",
                "error": repr(exc),
                "seconds": round(time.perf_counter() - started, 3),
            }
        )

    existing = ROOT / "artifacts" / "offline_metrics" / "predictions__demand_xgboost.csv"
    if existing.exists():
        baseline = pd.read_csv(existing)
        baseline = baseline[baseline["segment"].eq("Domestic")]
        leaderboard.append(
            experiment.score(test, baseline["prediction"].to_numpy(), "existing_domestic_demand_xgb")
        )

    frame = pd.DataFrame(leaderboard).sort_values("wmape")
    frame.to_csv(OUTPUT / "domestic_leaderboard.csv", index=False)
    pd.DataFrame(statuses).to_csv(OUTPUT / "domestic_pipeline_status.csv", index=False)
    print("\nDOMESTIC XGBOOST LEADERBOARD")
    print(
        frame[["model", "wmape", "bias_pct", "mae", "rmse"]].to_string(
            index=False, float_format=lambda value: f"{value:.6f}"
        )
    )


if __name__ == "__main__":
    main()

