from fastapi.testclient import TestClient

from prototype.api import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_options_have_dates_and_origins():
    response = client.get("/options")
    assert response.status_code == 200
    payload = response.json()
    assert payload["origins"]
    assert payload["markets"]
    assert payload["minimum_date"] <= payload["maximum_date"]
    assert payload["scenario_controls"] == [
        "mode",
        "start_date",
        "end_date",
        "origin_country",
        "target_nationality",
        "weekly_flights",
        "seats_per_flight",
        "load_factor",
        "transfer_share",
        "transit_share",
        "visitor_share",
        "hotel_capture_rate",
        "nationality_allocation_share",
    ]


def test_simulate_existing_route_reconciles():
    options = client.get("/options").json()
    origin = options["default_origin"]
    market = origin if origin in options["markets"] else options["markets"][0]
    response = client.post(
        "/simulate",
        json={
            "mode": "Existing route",
            "origin_country": origin,
            "target_nationality": market,
            "start_date": options["minimum_date"],
            "end_date": options["maximum_date"],
            "frequency_change_pct": 20,
            "transfer_share": 0.20,
            "transit_share": 0.02,
            "visitor_share": 0.75,
            "hotel_capture_rate": 0.65,
            "nationality_allocation_share": 1.0,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scenario_seats"] >= 0
    assert result["scenario_passengers"] >= 0
    assert result["scenario_guest_nights"] >= 0
    assert len(result["chain"]) == 6
    assert result["daily"]


def test_sensitivity_returns_ranked_complete_model_reruns():
    options = client.get("/options").json()
    response = client.post(
        "/sensitivity",
        json={
            "origin_country": options["default_origin"],
            "target_nationality": options["default_market"],
            "start_date": options["minimum_date"],
            "end_date": options["maximum_date"],
            "scenario_weekly_flights": options["default_scenario"]["scenario_weekly_flights"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["drivers"]) == 4
    swings = [driver["swing"] for driver in payload["drivers"]]
    assert swings == sorted(swings, reverse=True)
    # Existing-route load factor is a change in points, so -5 must lower demand.
    load_factor = next(d for d in payload["drivers"] if d["driver"] == "Load factor")
    assert load_factor["downside"] < 0 < load_factor["upside"]


def test_global_sensitivity_endpoint(monkeypatch):
    monkeypatch.setattr(
        "prototype.api.global_sensitivity",
        lambda payload: {
            "method": "SALib Morris elementary effects",
            "evaluations": 72,
            "drivers": [{"rank": 1, "driver": "Weekly flights", "mu_star": 10.0}],
        },
    )
    options = client.get("/options").json()
    response = client.post(
        "/global-sensitivity",
        json={
            "origin_country": options["default_origin"],
            "target_nationality": options["default_market"],
            "start_date": options["minimum_date"],
            "end_date": options["maximum_date"],
        },
    )
    assert response.status_code == 200
    assert response.json()["method"].startswith("SALib Morris")


def test_morris_ranks_dominant_factor_with_injected_evaluator():
    from prototype.service import global_sensitivity

    payload = {
        "mode": "New route",
        "origin_country": "TEST",
        "target_nationality": "TEST",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "new_route_weekly_flights": 2.0,
        "new_route_seats_per_flight": 180.0,
        "new_route_load_factor": 0.75,
        "transfer_share": 0.20,
        "transit_share": 0.02,
        "visitor_share": 0.75,
        "hotel_capture_rate": 0.65,
        "nationality_allocation_share": 0.50,
    }

    def evaluator(sample):
        return 1000.0 * sample["new_route_weekly_flights"] + sample["new_route_seats_per_flight"]

    result = global_sensitivity(payload, trajectories=6, evaluator=evaluator)
    assert result["evaluations"] == 54
    assert result["drivers"][0]["parameter"] == "new_route_weekly_flights"
    assert abs(sum(driver["relative_importance"] for driver in result["drivers"]) - 1.0) < 1e-9
