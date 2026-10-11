"""Core correctness checks for the isolated scenario prototype."""

from __future__ import annotations

import pandas as pd

from pipeline.modeling import ARTIFACT_DIR, MODEL_FEATURES, load_hotel_data, load_model
from prototype.scenario_engine import ScenarioInputs, distribute_arrival_delta, scenario_chain


def sample_inputs(**overrides) -> ScenarioInputs:
    values = {
        "mode": "Existing route",
        "origin_country": "INDIA",
        "target_nationality": "INDIA",
        "start_date": pd.Timestamp("2025-08-01"),
        "end_date": pd.Timestamp("2025-08-31"),
        "frequency_change_pct": 10.0,
        "seats_per_flight_change_pct": 0.0,
        "load_factor_change_points": 0.0,
        "transfer_share": 0.20,
        "transit_share": 0.02,
        "visitor_share": 0.75,
        "hotel_capture_rate": 0.65,
        "nationality_allocation_share": 1.0,
    }
    values.update(overrides)
    return ScenarioInputs(**values)


def test_scenario_chain_reconciles() -> None:
    baseline = {
        "seats": 10_000.0,
        "passengers": 8_000.0,
        "transfer": 1_600.0,
        "transit": 160.0,
        "load_factor": 0.80,
    }
    inputs = sample_inputs()
    chain = scenario_chain(baseline, inputs)
    assert chain["scenario_seats"] == 11_000.0
    assert chain["scenario_passengers"] == 8_800.0
    assert abs(chain["scenario_destination_passengers"] - 8_800.0 * 0.78) < 1e-9
    assert abs(chain["scenario_visitors"] - chain["scenario_destination_passengers"] * 0.75) < 1e-9
    assert abs(chain["scenario_hotel_arrivals"] - chain["scenario_visitors"] * 0.65) < 1e-9


def test_new_route_seats_use_frequency_and_gauge() -> None:
    inputs = sample_inputs(
        mode="New route",
        new_route_weekly_flights=2.0,
        new_route_seats_per_flight=200.0,
        new_route_load_factor=0.75,
    )
    chain = scenario_chain({}, inputs)
    expected_seats = 2.0 * (31 / 7) * 200.0
    assert abs(chain["scenario_seats"] - expected_seats) < 1e-9
    assert abs(chain["scenario_passengers"] - expected_seats * 0.75) < 1e-9


def test_arrival_delta_is_allocated_without_changing_other_markets() -> None:
    rows = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-08-01", "2025-08-02", "2025-08-01"]),
            "segment": ["International", "International", "International"],
            "market": ["INDIA", "INDIA", "CHINA"],
            "new_arrivals": [100.0, 300.0, 200.0],
        }
    )
    adjusted = distribute_arrival_delta(
        rows,
        "INDIA",
        pd.Timestamp("2025-08-01"),
        pd.Timestamp("2025-08-02"),
        80.0,
    )
    india_delta = adjusted.loc[adjusted["market"].eq("INDIA"), "new_arrivals"].sum() - 400.0
    assert abs(india_delta - 80.0) < 1e-9
    assert adjusted.loc[adjusted["market"].eq("CHINA"), "new_arrivals"].iloc[0] == 200.0


def test_current_target_is_not_a_model_feature() -> None:
    assert "guests" not in MODEL_FEATURES


def test_official_test_is_target_free_and_has_212_dates() -> None:
    _, test = load_hotel_data()
    assert "guests" not in test.columns
    assert test["date"].nunique() == 212
    assert test["date"].min() == pd.Timestamp("2025-08-01")
    assert test["date"].max() == pd.Timestamp("2026-02-28")


def test_trained_artifacts_exist() -> None:
    assert (ARTIFACT_DIR / "pooled_poisson_xgboost.joblib").exists()
    assert (ARTIFACT_DIR / "holdout_metrics.json").exists()


def test_served_artifact_is_the_selected_pooled_poisson_model() -> None:
    model = load_model()
    estimator = model.named_steps["model"]
    assert estimator.get_params()["objective"] == "count:poisson"
    assert len(MODEL_FEATURES) == 14
    assert "segment" in MODEL_FEATURES
