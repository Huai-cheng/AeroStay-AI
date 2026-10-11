"""Transparent aviation conversion and scenario-to-arrival transformations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class ScenarioInputs:
    mode: str
    origin_country: str
    target_nationality: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    frequency_change_pct: float
    seats_per_flight_change_pct: float
    load_factor_change_points: float
    transfer_share: float
    transit_share: float
    visitor_share: float
    hotel_capture_rate: float
    nationality_allocation_share: float
    new_route_weekly_flights: float = 2.0
    new_route_seats_per_flight: float = 180.0
    new_route_load_factor: float = 0.75


def load_flights() -> pd.DataFrame:
    frame = pd.read_excel(DATA_DIR / "flight_data.xlsx")
    frame["Date"] = pd.to_datetime(frame["Date"])
    numeric = [
        "Average Weekly Frequency",
        "Load Factor",
        "Total P2P",
        "Total PAX",
        "Total Seats",
        "Total Transfer",
        "Total Transit",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["Origin Key"] = frame["Departure Country Name"].astype(str).str.upper().str.strip()
    return frame


def available_origins(flights: pd.DataFrame) -> list[str]:
    return sorted(flights["Origin Key"].dropna().unique().tolist())


def aggregate_origin_baseline(
    flights: pd.DataFrame,
    origin: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> dict[str, float]:
    mask = (
        flights["Origin Key"].eq(origin)
        & flights["Date"].between(start_date, end_date)
    )
    part = flights.loc[mask].copy()
    if part.empty:
        return {
            "rows": 0,
            "seats": 0.0,
            "passengers": 0.0,
            "p2p": 0.0,
            "transfer": 0.0,
            "transit": 0.0,
            "load_factor": 0.0,
            "transfer_share": 0.0,
            "transit_share": 0.0,
            "average_weekly_frequency": 0.0,
        }
    seats = float(part["Total Seats"].sum())
    passengers = float(part["Total PAX"].sum())
    transfer = float(part["Total Transfer"].sum())
    transit = float(part["Total Transit"].sum())
    daily_frequency = part.groupby("Date")["Average Weekly Frequency"].sum(min_count=1)
    return {
        "rows": int(len(part)),
        "seats": seats,
        "passengers": passengers,
        "p2p": float(part["Total P2P"].sum()),
        "transfer": transfer,
        "transit": transit,
        "load_factor": passengers / max(seats, 1.0),
        "transfer_share": transfer / max(passengers, 1.0),
        "transit_share": transit / max(passengers, 1.0),
        "average_weekly_frequency": float(daily_frequency.mean())
        if daily_frequency.notna().any()
        else 0.0,
    }


def scenario_chain(
    baseline: dict[str, float],
    inputs: ScenarioInputs,
    *,
    visitor_share: float | None = None,
    hotel_capture_rate: float | None = None,
) -> dict[str, float]:
    visitor_share = inputs.visitor_share if visitor_share is None else visitor_share
    hotel_capture_rate = (
        inputs.hotel_capture_rate if hotel_capture_rate is None else hotel_capture_rate
    )
    days = (inputs.end_date - inputs.start_date).days + 1
    weeks = days / 7.0

    if inputs.mode == "New route":
        baseline_seats = 0.0
        baseline_passengers = 0.0
        baseline_destination = 0.0
        scenario_seats = (
            inputs.new_route_weekly_flights
            * weeks
            * inputs.new_route_seats_per_flight
        )
        scenario_load_factor = inputs.new_route_load_factor
    else:
        baseline_seats = baseline["seats"]
        baseline_passengers = baseline["passengers"]
        baseline_destination = max(
            0.0,
            baseline_passengers - baseline["transfer"] - baseline["transit"],
        )
        frequency_factor = max(0.0, 1.0 + inputs.frequency_change_pct / 100.0)
        gauge_factor = max(0.0, 1.0 + inputs.seats_per_flight_change_pct / 100.0)
        scenario_seats = baseline_seats * frequency_factor * gauge_factor
        scenario_load_factor = np.clip(
            baseline["load_factor"] + inputs.load_factor_change_points / 100.0,
            0.0,
            1.25,
        )

    scenario_passengers = scenario_seats * scenario_load_factor
    flow_share = max(0.0, 1.0 - inputs.transfer_share - inputs.transit_share)
    scenario_destination = scenario_passengers * flow_share
    baseline_visitors = baseline_destination * visitor_share
    scenario_visitors = scenario_destination * visitor_share
    baseline_hotel_arrivals = baseline_visitors * hotel_capture_rate
    scenario_hotel_arrivals = scenario_visitors * hotel_capture_rate
    allocated_delta = (
        scenario_hotel_arrivals - baseline_hotel_arrivals
    ) * inputs.nationality_allocation_share

    return {
        "baseline_seats": baseline_seats,
        "scenario_seats": scenario_seats,
        "baseline_passengers": baseline_passengers,
        "scenario_passengers": scenario_passengers,
        "baseline_destination_passengers": baseline_destination,
        "scenario_destination_passengers": scenario_destination,
        "baseline_visitors": baseline_visitors,
        "scenario_visitors": scenario_visitors,
        "baseline_hotel_arrivals": baseline_hotel_arrivals,
        "scenario_hotel_arrivals": scenario_hotel_arrivals,
        "allocated_arrival_delta": allocated_delta,
        "scenario_load_factor": float(scenario_load_factor),
        "assumed_visitor_share": float(visitor_share),
        "assumed_hotel_capture_rate": float(hotel_capture_rate),
    }


def distribute_arrival_delta(
    test_rows: pd.DataFrame,
    target_nationality: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    total_delta: float,
) -> pd.DataFrame:
    result = test_rows.copy()
    mask = (
        result["segment"].eq("International")
        & result["market"].eq(target_nationality)
        & result["date"].between(start_date, end_date)
    )
    selected = result.loc[mask, "new_arrivals"].fillna(0).clip(lower=0)
    if selected.empty:
        raise ValueError("The selected nationality has no hotel rows in this period")
    if selected.sum() > 0:
        weights = selected / selected.sum()
    else:
        weights = pd.Series(1.0 / len(selected), index=selected.index)
    result.loc[mask, "new_arrivals"] = np.clip(
        selected.to_numpy() + total_delta * weights.to_numpy(), 0.0, None
    )
    return result


def scenario_record(inputs: ScenarioInputs, chain: dict[str, float]) -> dict:
    record = asdict(inputs)
    for key in ("start_date", "end_date"):
        record[key] = str(pd.Timestamp(record[key]).date())
    record.update(chain)
    return record

