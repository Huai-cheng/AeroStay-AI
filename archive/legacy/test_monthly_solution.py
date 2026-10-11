import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from dtc.model import metrics
from dtc.scenario import ScenarioRequest, simulate


def test_wmape_and_bias_have_expected_units():
    result = metrics(np.array([100, 200]), np.array([90, 210]))
    assert result["wmape_percent"] == pytest.approx(100 * 20 / 300)
    assert result["bias_percent"] == pytest.approx(0)


def test_scenario_chain_and_market_totals(monkeypatch):
    fake_rows = pd.DataFrame([
        {"nationality": "INDIA", "predicted_arrivals": 1000.0,
         "predicted_guest_days": 3000.0, "direct_origin_seats": 10000.0},
        {"nationality": "FRANCE", "predicted_arrivals": 500.0,
         "predicted_guest_days": 1500.0, "direct_origin_seats": 2000.0},
    ])
    monkeypatch.setattr("dtc.scenario.baseline_predictions", lambda *_: fake_rows)
    bundle = {
        "manifest": {"run_id": "test-run", "serving_train_end": "2025-07-01"},
        "reference": {
            "origin_rates": {"INDIA": {"load_factor": 0.8, "transfer_transit_share": 0.25}},
            "pooled_origin_rates": {"load_factor": 0.8, "transfer_transit_share": 0.25},
            "nonresident_visitor_share_assumed": 0.8,
            "hotel_capture_rate_derived": 0.5,
            "effective_hotel_conversion_from_p2p": 0.4,
            "effective_conversion_monthly_p10_p90": [0.32, 0.48],
            "stay_proxy_global": 3.0,
            "same_origin_nationality_share_assumed": 0.75,
            "hotel_nationality_shares": {"INDIA": 0.6, "FRANCE": 0.4},
        },
    }
    result = simulate({}, bundle, ScenarioRequest(
        month="2025-12", departure_country="India", flights_per_week_delta=2,
        seats_per_flight=200,
    ))
    chain = result["chain_change"]
    assert chain["arriving_passengers"] == pytest.approx(chain["scheduled_seats"] * 0.8)
    assert chain["point_to_point_passengers"] == pytest.approx(chain["arriving_passengers"] * 0.75)
    assert chain["estimated_inbound_visitors"] == pytest.approx(chain["point_to_point_passengers"] * 0.8)
    assert chain["estimated_hotel_checkins"] == pytest.approx(chain["estimated_inbound_visitors"] * 0.5)
    assert result["change"]["estimated_guest_nights"] == pytest.approx(chain["estimated_hotel_checkins"] * 3)
    assert sum(row["change_hotel_checkins"] for row in result["market_results"]) == pytest.approx(result["change"]["hotel_checkins"])


def test_invalid_rate_is_rejected():
    with pytest.raises(ValidationError):
        ScenarioRequest(month="2025-12", departure_country="India", flights_per_week_delta=2,
                        seats_per_flight=200, load_factor=1.2)
