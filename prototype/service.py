"""Shared, serialisable application service for Streamlit and HTTP clients."""

from __future__ import annotations

from functools import lru_cache
import json
import os
from typing import Any

import joblib
import numpy as np
import pandas as pd
from SALib.analyze import morris as morris_analyze
from SALib.sample import morris as morris_sample

from pipeline.modeling import (
    ARTIFACT_DIR,
    build_features,
    load_hotel_data,
    load_model,
    predict_with_model,
)
from prototype.scenario_engine import (
    ScenarioInputs,
    aggregate_origin_baseline,
    available_origins,
    distribute_arrival_delta,
    load_flights,
    scenario_chain,
    scenario_record,
)

# Public UI contract. Streamlit and the custom dashboard must expose these
# controls with the same meaning. See UI_SCENARIO_PARITY.md.
SCENARIO_CONTROL_KEYS = [
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


# Optional pre-built copy of application_state(). Deployments write it at build
# time so a cold serverless instance skips re-parsing the workbooks.
STATE_SNAPSHOT = ARTIFACT_DIR / "application_state.joblib"


@lru_cache(maxsize=1)
def application_state() -> dict[str, Any]:
    if os.environ.get("AEROSTAY_USE_STATE_SNAPSHOT") == "1" and STATE_SNAPSHOT.exists():
        return joblib.load(STATE_SNAPSHOT)
    return build_application_state()


def write_state_snapshot() -> None:
    joblib.dump(build_application_state(), STATE_SNAPSHOT)


def build_application_state() -> dict[str, Any]:
    train, test = load_hotel_data()
    flights = load_flights()
    model = load_model()
    metadata = json.loads((ARTIFACT_DIR / "model_metadata.json").read_text(encoding="utf-8"))
    metrics = json.loads((ARTIFACT_DIR / "holdout_metrics.json").read_text(encoding="utf-8"))
    baseline = predict_frame(model, train, test)
    return {
        "train": train,
        "test": test,
        "flights": flights,
        "model": model,
        "metadata": metadata,
        "metrics": metrics,
        "baseline": baseline,
    }


def predict_frame(model, train: pd.DataFrame, raw_test: pd.DataFrame) -> pd.DataFrame:
    features = build_features(raw_test, train, origin_date=train["date"].min())
    prediction = predict_with_model(model, features)
    output = features[
        ["date", "segment", "market", "new_arrivals", "same_day_guests", "same_day_missing"]
    ].copy()
    output["predicted_guests"] = prediction
    output["predicted_guest_nights"] = np.clip(
        output["predicted_guests"] - output["same_day_guests"].fillna(0), 0.0, None
    )
    return output


def selected_total(frame: pd.DataFrame, inputs: ScenarioInputs, column: str) -> float:
    mask = frame["date"].between(inputs.start_date, inputs.end_date)
    return float(frame.loc[mask, column].sum())


def selected_market_total(frame: pd.DataFrame, inputs: ScenarioInputs, column: str) -> float:
    mask = (
        frame["date"].between(inputs.start_date, inputs.end_date)
        & frame["segment"].eq("International")
        & frame["market"].eq(inputs.target_nationality)
    )
    return float(frame.loc[mask, column].sum())


def scenario_prediction(model, train, raw_test, inputs: ScenarioInputs, chain: dict) -> pd.DataFrame:
    adjusted = distribute_arrival_delta(
        raw_test,
        inputs.target_nationality,
        inputs.start_date,
        inputs.end_date,
        chain["allocated_arrival_delta"],
    )
    return predict_frame(model, train, adjusted)


def options_payload() -> dict[str, Any]:
    state = application_state()
    test = state["test"]
    markets = sorted(test.loc[test["segment"].eq("International"), "market"].unique().tolist())
    origins = available_origins(state["flights"])
    default_origin = "INDIA" if "INDIA" in origins else origins[0]
    minimum_date = test["date"].min()
    maximum_date = test["date"].max()
    default_flight = aggregate_origin_baseline(
        state["flights"], default_origin, minimum_date, maximum_date
    )
    route_baselines = {}
    for origin in origins:
        route = aggregate_origin_baseline(state["flights"], origin, minimum_date, maximum_date)
        route_baselines[origin] = {
            "weekly_flights": float(route["average_weekly_frequency"]),
            "load_factor": float(route["load_factor"]),
            "transfer_share": float(route["transfer_share"]),
            "transit_share": float(route["transit_share"]),
        }
    return {
        "scenario_controls": SCENARIO_CONTROL_KEYS,
        "origins": origins,
        "markets": markets,
        "unserved_markets": [market for market in markets if market not in origins],
        "minimum_date": str(minimum_date.date()),
        "maximum_date": str(maximum_date.date()),
        "default_origin": default_origin,
        "default_market": default_origin if default_origin in markets else markets[0],
        "route_baselines": route_baselines,
        "default_scenario": {
            "baseline_weekly_flights": float(default_flight["average_weekly_frequency"]),
            "scenario_weekly_flights": float(default_flight["average_weekly_frequency"] + 2.0),
            "transfer_share": float(default_flight["transfer_share"]),
            "transit_share": float(default_flight["transit_share"]),
            "visitor_share": 0.75,
            "hotel_capture_rate": 0.65,
            "nationality_allocation_share": 1.0,
        },
    }


def prepare_scenario(payload: dict[str, Any]) -> tuple[dict[str, Any], ScenarioInputs, dict, dict, float | None, float]:
    """Resolve a request into the shared model/scenario objects used by every analysis."""
    state = application_state()
    start_date = pd.Timestamp(payload["start_date"])
    end_date = pd.Timestamp(payload["end_date"])
    mode = payload.get("mode", "Existing route")
    baseline_flight = aggregate_origin_baseline(
        state["flights"], payload["origin_country"], start_date, end_date
    )
    requested_weekly = payload.get("scenario_weekly_flights")
    frequency_change = float(payload.get("frequency_change_pct", 0.0))
    if mode == "Existing route" and requested_weekly is not None:
        base_weekly = baseline_flight["average_weekly_frequency"]
        frequency_change = ((float(requested_weekly) / base_weekly) - 1.0) * 100 if base_weekly else 0.0

    transfer_share = payload.get("transfer_share")
    transit_share = payload.get("transit_share")
    inputs = ScenarioInputs(
        mode=mode,
        origin_country=payload["origin_country"],
        target_nationality=payload["target_nationality"],
        start_date=start_date,
        end_date=end_date,
        frequency_change_pct=frequency_change,
        seats_per_flight_change_pct=float(payload.get("seats_per_flight_change_pct", 0.0)),
        load_factor_change_points=float(payload.get("load_factor_change_points", 0.0)),
        transfer_share=float(baseline_flight["transfer_share"] if transfer_share is None else transfer_share),
        transit_share=float(baseline_flight["transit_share"] if transit_share is None else transit_share),
        visitor_share=float(payload.get("visitor_share", 0.75)),
        hotel_capture_rate=float(payload.get("hotel_capture_rate", 0.65)),
        nationality_allocation_share=float(payload.get("nationality_allocation_share", 1.0)),
        new_route_weekly_flights=float(payload.get("new_route_weekly_flights", 2.0)),
        new_route_seats_per_flight=float(payload.get("new_route_seats_per_flight", 180.0)),
        new_route_load_factor=float(payload.get("new_route_load_factor", 0.75)),
    )
    chain = scenario_chain(baseline_flight, inputs)
    return state, inputs, chain, baseline_flight, requested_weekly, frequency_change


def _selected_market_scenario_nights(payload: dict[str, Any]) -> float:
    """Run one model evaluation without the planning-range calculations."""
    state, inputs, chain, _, _, _ = prepare_scenario(payload)
    frame = scenario_prediction(state["model"], state["train"], state["test"], inputs, chain)
    return selected_market_total(frame, inputs, "predicted_guest_nights")


def simulate(payload: dict[str, Any]) -> dict[str, Any]:
    state, inputs, chain, baseline_flight, requested_weekly, frequency_change = prepare_scenario(payload)
    mode = inputs.mode
    start_date = inputs.start_date
    end_date = inputs.end_date
    scenario_frame = scenario_prediction(state["model"], state["train"], state["test"], inputs, chain)
    baseline_frame = state["baseline"]

    low_chain = scenario_chain(
        baseline_flight,
        inputs,
        visitor_share=max(0.0, inputs.visitor_share - 0.10),
        hotel_capture_rate=max(0.0, inputs.hotel_capture_rate - 0.10),
    )
    high_chain = scenario_chain(
        baseline_flight,
        inputs,
        visitor_share=min(1.0, inputs.visitor_share + 0.10),
        hotel_capture_rate=min(1.0, inputs.hotel_capture_rate + 0.10),
    )
    low_frame = scenario_prediction(state["model"], state["train"], state["test"], inputs, low_chain)
    high_frame = scenario_prediction(state["model"], state["train"], state["test"], inputs, high_chain)

    baseline_guests = selected_total(baseline_frame, inputs, "predicted_guests")
    scenario_guests = selected_total(scenario_frame, inputs, "predicted_guests")
    baseline_nights = selected_total(baseline_frame, inputs, "predicted_guest_nights")
    scenario_nights = selected_total(scenario_frame, inputs, "predicted_guest_nights")
    assumption_low = selected_total(low_frame, inputs, "predicted_guest_nights")
    assumption_high = selected_total(high_frame, inputs, "predicted_guest_nights")
    route_uncertainty = 1.25 if mode == "New route" else 1.0
    planning_low = max(
        0.0,
        min(assumption_low, assumption_high)
        * (1.0 - min(0.8, state["metrics"]["combined"]["wmape"] * route_uncertainty)),
    )
    planning_high = max(assumption_low, assumption_high) * (
        1.0 + state["metrics"]["combined"]["wmape"] * route_uncertainty
    )

    mask = baseline_frame["date"].between(start_date, end_date)
    baseline_daily = baseline_frame.loc[mask].groupby("date")["predicted_guest_nights"].sum()
    scenario_daily = scenario_frame.loc[mask].groupby("date")["predicted_guest_nights"].sum()
    daily = [
        {"date": str(date.date()), "baseline": float(value), "scenario": float(scenario_daily.loc[date])}
        for date, value in baseline_daily.items()
    ]
    monthly_frame = pd.DataFrame(daily)
    monthly_frame["month"] = pd.to_datetime(monthly_frame["date"]).dt.to_period("M").astype(str)
    monthly = monthly_frame.groupby("month", as_index=False)[["baseline", "scenario"]].sum()

    chain_rows = [
        ("Scheduled seats", "baseline_seats", "scenario_seats", "Observed / schedule-derived"),
        ("Passenger movements", "baseline_passengers", "scenario_passengers", "Load-factor conversion"),
        ("Destination passengers", "baseline_destination_passengers", "scenario_destination_passengers", "Transfer/transit adjustment"),
        ("Inbound visitors", "baseline_visitors", "scenario_visitors", "Planner assumption"),
        ("Hotel guest arrivals", "baseline_hotel_arrivals", "scenario_hotel_arrivals", "Planner assumption"),
        ("Predicted guest nights", None, None, "Pooled Poisson XGBoost"),
    ]
    selected_baseline = selected_market_total(baseline_frame, inputs, "predicted_guest_nights")
    selected_scenario = selected_market_total(scenario_frame, inputs, "predicted_guest_nights")
    chain_payload = []
    for label, base_key, scenario_key, source in chain_rows:
        base = selected_baseline if base_key is None else float(chain[base_key])
        scenario_value = selected_scenario if scenario_key is None else float(chain[scenario_key])
        chain_payload.append(
            {"stage": label, "baseline": base, "scenario": scenario_value, "change": scenario_value - base, "source": source}
        )

    checks: list[dict[str, str]] = []
    if mode == "New route":
        checks.append({"level": "warning", "message": "Unseen route: pooled behavior and a wider scenario range are used."})
    if inputs.origin_country != inputs.target_nationality:
        checks.append({"level": "info", "message": "Departure origin and hotel nationality are linked through an explicit allocation assumption."})
    if baseline_frame.loc[mask, "same_day_missing"].sum() > 0:
        checks.append({"level": "info", "message": "Missing same-day observations increase target uncertainty."})

    result = scenario_record(inputs, chain)
    result.update(
        {
            "model_version": state["metadata"].get("approach", "Pooled Poisson XGBoost"),
            "baseline_weekly_flights": float(baseline_flight["average_weekly_frequency"]),
            "scenario_weekly_flights": float(
                inputs.new_route_weekly_flights
                if mode == "New route"
                else (
                    requested_weekly
                    if requested_weekly is not None
                    else baseline_flight["average_weekly_frequency"] * (1.0 + frequency_change / 100.0)
                )
            ),
            "baseline_predicted_guests": baseline_guests,
            "scenario_predicted_guests": scenario_guests,
            "baseline_guest_nights": baseline_nights,
            "scenario_guest_nights": scenario_nights,
            "selected_market_baseline_nights": selected_baseline,
            "selected_market_scenario_nights": selected_scenario,
            "planning_range_low": planning_low,
            "planning_range_high": planning_high,
            "chain": chain_payload,
            "daily": daily,
            "monthly": monthly.to_dict(orient="records"),
            "checks": checks,
            "metrics": state["metrics"],
        }
    )
    return result


def sensitivity(payload: dict[str, Any]) -> dict[str, Any]:
    """One-at-a-time stress test around the submitted scenario.

    The endpoint deliberately reruns the complete conversion and XGBoost path so
    the displayed driver effects are model outputs, not front-end approximations.
    """
    base = simulate(payload)
    base_value = float(base["selected_market_scenario_nights"])
    mode = payload.get("mode", "Existing route")
    weekly_key = "new_route_weekly_flights" if mode == "New route" else "scenario_weekly_flights"
    weekly_value = float(payload.get(weekly_key) or base["scenario_weekly_flights"])
    load_factor_key = "new_route_load_factor" if mode == "New route" else "load_factor_change_points"
    load_factor_base = (
        float(payload.get("new_route_load_factor", 0.75))
        if mode == "New route"
        else float(payload.get("load_factor_change_points", 0.0))
    )
    # New routes perturb an absolute load factor; existing routes perturb a change
    # in percentage points, which may be negative (scenario_chain clips the result).
    if mode == "New route":
        load_factor_low = max(0.0, load_factor_base - 0.05)
        load_factor_high = min(1.25, load_factor_base + 0.05)
    else:
        load_factor_low = load_factor_base - 5.0
        load_factor_high = load_factor_base + 5.0
    cases = [
        ("Weekly flights", weekly_key, max(0.0, weekly_value - 2.0), weekly_value + 2.0, "±2 flights/week"),
        ("Load factor", load_factor_key, load_factor_low, load_factor_high, "±5 percentage points"),
        ("Visitor share", "visitor_share", max(0.0, float(payload.get("visitor_share", 0.75)) - 0.10), min(1.0, float(payload.get("visitor_share", 0.75)) + 0.10), "±10 percentage points"),
        ("Hotel capture", "hotel_capture_rate", max(0.0, float(payload.get("hotel_capture_rate", 0.65)) - 0.10), min(1.0, float(payload.get("hotel_capture_rate", 0.65)) + 0.10), "±10 percentage points"),
    ]
    drivers = []
    for label, key, low_value, high_value, perturbation in cases:
        low_payload = {**payload, key: low_value}
        high_payload = {**payload, key: high_value}
        low = float(simulate(low_payload)["selected_market_scenario_nights"])
        high = float(simulate(high_payload)["selected_market_scenario_nights"])
        drivers.append(
            {
                "driver": label,
                "perturbation": perturbation,
                "low": low,
                "base": base_value,
                "high": high,
                "downside": low - base_value,
                "upside": high - base_value,
                "swing": abs(high - low),
            }
        )
    drivers.sort(key=lambda item: item["swing"], reverse=True)
    return {"base": base_value, "drivers": drivers}


def _bounded(center: float, radius: float, minimum: float, maximum: float) -> list[float]:
    low = max(minimum, center - radius)
    high = min(maximum, center + radius)
    if high - low < 1e-9:
        high = min(maximum, low + max(radius, 1e-3))
        low = max(minimum, high - max(radius, 1e-3))
    return [float(low), float(high)]


def morris_problem(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Define plausible, documented analysis bounds around the submitted scenario."""
    mode = payload.get("mode", "Existing route")
    if mode == "New route":
        aviation = [
            ("new_route_weekly_flights", "Weekly flights", float(payload.get("new_route_weekly_flights", 2.0)), 2.0, 0.0, 100.0),
            ("new_route_seats_per_flight", "Seats per flight", float(payload.get("new_route_seats_per_flight", 180.0)), 50.0, 50.0, 600.0),
            ("new_route_load_factor", "Load factor", float(payload.get("new_route_load_factor", 0.75)), 0.10, 0.30, 1.0),
        ]
    else:
        state = application_state()
        baseline = aggregate_origin_baseline(
            state["flights"], payload["origin_country"], pd.Timestamp(payload["start_date"]), pd.Timestamp(payload["end_date"])
        )
        weekly = float(payload.get("scenario_weekly_flights") or baseline["average_weekly_frequency"])
        aviation = [
            ("scenario_weekly_flights", "Weekly flights", weekly, 2.0, 0.0, 1000.0),
            ("seats_per_flight_change_pct", "Seats-per-flight change", float(payload.get("seats_per_flight_change_pct", 0.0)), 20.0, -40.0, 60.0),
            ("load_factor_change_points", "Load-factor change", float(payload.get("load_factor_change_points", 0.0)), 5.0, -20.0, 20.0),
        ]

    transfer = float(payload.get("transfer_share") or 0.0)
    transit = float(payload.get("transit_share") or 0.0)
    transfer_bounds = _bounded(transfer, 0.10, 0.0, min(0.90, 0.97 - max(0.0, transit - 0.05)))
    transit_bounds = _bounded(transit, 0.05, 0.0, min(0.25, 0.97 - transfer_bounds[1]))
    definitions = aviation + [
        ("transfer_share", "Transfer share", transfer, 0.10, transfer_bounds[0], transfer_bounds[1]),
        ("transit_share", "Transit share", transit, 0.05, transit_bounds[0], transit_bounds[1]),
        ("visitor_share", "Visitor share", float(payload.get("visitor_share", 0.75)), 0.15, 0.20, 1.0),
        ("hotel_capture_rate", "Hotel-capture rate", float(payload.get("hotel_capture_rate", 0.65)), 0.15, 0.10, 1.0),
        ("nationality_allocation_share", "Origin-to-nationality allocation", float(payload.get("nationality_allocation_share", 1.0)), 0.20, 0.10, 1.0),
    ]
    factors = []
    for key, label, center, radius, minimum, maximum in definitions:
        bounds = [minimum, maximum] if key in {"transfer_share", "transit_share"} else _bounded(center, radius, minimum, maximum)
        factors.append({"key": key, "label": label, "bounds": bounds})
    return {
        "num_vars": len(factors),
        "names": [factor["key"] for factor in factors],
        "bounds": [factor["bounds"] for factor in factors],
    }, factors


def global_sensitivity(payload: dict[str, Any], *, trajectories: int = 8, evaluator=None) -> dict[str, Any]:
    """Rank inputs with SALib Morris; sigma flags interaction/non-linearity."""
    problem, factors = morris_problem(payload)
    samples = morris_sample.sample(problem, N=trajectories, num_levels=4, seed=42)
    evaluate = evaluator or _selected_market_scenario_nights
    outputs = np.asarray(
        [evaluate({**payload, **dict(zip(problem["names"], row, strict=True))}) for row in samples], dtype=float
    )
    indices = morris_analyze.analyze(
        problem, samples, outputs, num_levels=4, print_to_console=False, seed=42
    )
    mu_star = np.asarray(indices["mu_star"], dtype=float)
    denominator = float(np.nansum(mu_star)) or 1.0
    drivers = []
    for index, factor in enumerate(factors):
        drivers.append({
            "driver": factor["label"],
            "parameter": factor["key"],
            "bounds": factor["bounds"],
            "mu": float(np.nan_to_num(indices["mu"][index])),
            "mu_star": float(np.nan_to_num(mu_star[index])),
            "mu_star_conf": float(np.nan_to_num(indices["mu_star_conf"][index])),
            "sigma": float(np.nan_to_num(indices["sigma"][index])),
            "relative_importance": float(np.nan_to_num(mu_star[index]) / denominator),
        })
    drivers.sort(key=lambda item: item["mu_star"], reverse=True)
    for rank, driver in enumerate(drivers, start=1):
        driver["rank"] = rank
    return {
        "method": "SALib Morris elementary effects",
        "output": "Selected-market scenario guest nights",
        "trajectories": trajectories,
        "evaluations": int(len(samples)),
        "drivers": drivers,
        "interpretation": "mu_star ranks overall influence; sigma indicates interaction or non-linearity.",
    }
