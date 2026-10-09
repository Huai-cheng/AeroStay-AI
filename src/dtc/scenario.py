"""Auditable scenario chain layered on the trained baseline forecast."""

from __future__ import annotations

import calendar
from typing import Any

from pydantic import BaseModel, Field, field_validator

from dtc.model import baseline_predictions


class ScenarioRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    departure_country: str = Field(min_length=2)
    departure_city: str | None = None
    flights_per_week_delta: float = Field(ge=-100, le=100)
    seats_per_flight: int = Field(gt=0, le=1000)
    load_factor: float | None = Field(default=None, ge=0, le=1)
    transfer_transit_share: float | None = Field(default=None, ge=0, le=1)
    nonresident_visitor_share: float | None = Field(default=None, ge=0, le=1)
    hotel_capture_rate: float | None = Field(default=None, ge=0, le=1)
    average_length_of_stay: float | None = Field(default=None, gt=0, le=60)
    same_origin_nationality_share: float | None = Field(default=None, ge=0, le=1)

    @field_validator("departure_country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return " ".join(value.upper().split())


def _allocation(origin: str, share: float, market_shares: dict[str, float]) -> tuple[dict[str, float], bool]:
    mapped = origin in market_shares
    allocation = {market: (1 - share) * fraction for market, fraction in market_shares.items()}
    local_market = origin if mapped else "OTHER_UNKNOWN"
    allocation[local_market] = allocation.get(local_market, 0.0) + share
    total = sum(allocation.values())
    return {market: fraction / total for market, fraction in allocation.items()}, mapped


def simulate(config: dict[str, Any], bundle: dict[str, Any], request: ScenarioRequest) -> dict[str, Any]:
    rows = baseline_predictions(config, bundle, request.month)
    reference = bundle["reference"]
    origin_rates = reference["origin_rates"].get(request.departure_country, reference["pooled_origin_rates"])
    load_factor = float(request.load_factor if request.load_factor is not None else origin_rates["load_factor"])
    transfer_share = float(request.transfer_transit_share if request.transfer_transit_share is not None else origin_rates["transfer_transit_share"])
    visitor_share = float(request.nonresident_visitor_share if request.nonresident_visitor_share is not None else reference["nonresident_visitor_share_assumed"])
    capture = float(request.hotel_capture_rate if request.hotel_capture_rate is not None else reference["hotel_capture_rate_derived"])
    stay = float(request.average_length_of_stay if request.average_length_of_stay is not None else reference["stay_proxy_global"])
    local_share = float(request.same_origin_nationality_share if request.same_origin_nationality_share is not None else reference["same_origin_nationality_share_assumed"])
    if not 0 <= load_factor <= 1:
        raise ValueError("Estimated origin load factor is outside 0–1; provide a scenario load_factor")
    if not 0 <= transfer_share <= 1 or not 0 <= capture <= 1 or not 0 <= visitor_share <= 1:
        raise ValueError("A calibrated rate is outside 0–1; revise model assumptions")

    year, month_number = map(int, request.month.split("-"))
    weeks = calendar.monthrange(year, month_number)[1] / 7
    delta_seats = request.flights_per_week_delta * weeks * request.seats_per_flight
    available_origin_seats = float(rows.loc[rows["nationality"].eq(request.departure_country), "direct_origin_seats"].sum())
    if delta_seats < -available_origin_seats:
        raise ValueError("Removed seats exceed observed seats for this departure country and month")
    delta_passengers = delta_seats * load_factor
    delta_p2p = delta_passengers * (1 - transfer_share)
    delta_visitors = delta_p2p * visitor_share
    delta_guests = delta_visitors * capture
    delta_guest_days = delta_guests * stay

    allocation, mapped = _allocation(request.departure_country, local_share, reference["hotel_nationality_shares"])
    baseline = {
        str(row.nationality): {
            "hotel_checkins": float(row.predicted_arrivals),
            "estimated_guest_nights": float(row.predicted_guest_days),
        }
        for row in rows.itertuples()
    }
    markets = []
    for nationality in sorted(set(baseline) | set(allocation)):
        base = baseline.get(nationality, {"hotel_checkins": 0.0, "estimated_guest_nights": 0.0})
        weight = allocation.get(nationality, 0.0)
        guest_delta = delta_guests * weight
        nights_delta = delta_guest_days * weight
        if base["hotel_checkins"] + guest_delta < -1e-6 or base["estimated_guest_nights"] + nights_delta < -1e-6:
            raise ValueError("Route reduction exceeds predicted hotel demand in an allocated market")
        markets.append({
            "guest_nationality": nationality,
            "allocation_share": weight,
            "baseline_hotel_checkins": base["hotel_checkins"],
            "scenario_hotel_checkins": base["hotel_checkins"] + guest_delta,
            "change_hotel_checkins": guest_delta,
            "baseline_estimated_guest_nights": base["estimated_guest_nights"],
            "scenario_estimated_guest_nights": base["estimated_guest_nights"] + nights_delta,
            "change_estimated_guest_nights": nights_delta,
        })
    baseline_guests = float(sum(item["baseline_hotel_checkins"] for item in markets))
    baseline_nights = float(sum(item["baseline_estimated_guest_nights"] for item in markets))
    warnings = [
        "Flight departure country is not observed hotel guest nationality; market allocation is an assumption.",
        "Guest nights use a guest-days/arrivals stay proxy; exact overnight nights were not supplied.",
        "Scenario change assumes added seats create proportional new passengers; displacement from other routes is not measured.",
    ]
    if not mapped:
        warnings.append("This departure country has no matching hotel nationality; the same-origin allocation goes to OTHER_UNKNOWN.")
    if request.departure_country not in reference["origin_rates"]:
        warnings.append("No origin-specific history; pooled load and transfer rates were used.")
    if request.month > bundle["manifest"]["serving_train_end"][:7]:
        warnings.append("This month is outside the serving model training period; estimate is a forecast.")

    # Historical monthly conversion variation. This excludes baseline forecast
    # error and causal uncertainty, so it is not a confidence interval.
    historical_low, historical_high = reference["effective_conversion_monthly_p10_p90"]
    effective = reference["effective_hotel_conversion_from_p2p"]
    low_multiplier = historical_low / effective if effective else 0.0
    high_multiplier = historical_high / effective if effective else 0.0
    if not mapped or request.departure_country not in reference["origin_rates"]:
        low_multiplier *= 0.5
        high_multiplier *= 1.5
    low_delta = delta_guest_days * low_multiplier
    high_delta = delta_guest_days * high_multiplier
    range_values = sorted([baseline_nights + low_delta, baseline_nights + high_delta])
    # Planner-sized one-factor changes. These are local scenario sensitivities,
    # not global causal importance or model feature importance.
    abs_seats = abs(delta_seats)
    abs_flights = abs(request.flights_per_week_delta)
    steps = [
        ("flights_per_week", "+1 flight/week", weeks * request.seats_per_flight * load_factor * (1 - transfer_share) * visitor_share * capture),
        ("seats_per_flight", "+50 seats/flight", abs_flights * weeks * 50 * load_factor * (1 - transfer_share) * visitor_share * capture),
        ("load_factor", "+10 percentage points", abs_seats * min(0.10, 1 - load_factor) * (1 - transfer_share) * visitor_share * capture),
        ("transfer_transit_share", "+10 percentage points", abs_seats * load_factor * min(0.10, 1 - transfer_share) * visitor_share * capture),
        ("nonresident_visitor_share", "+10 percentage points", abs_seats * load_factor * (1 - transfer_share) * min(0.10, 1 - visitor_share) * capture),
        ("hotel_capture_rate", "+10 percentage points", abs_seats * load_factor * (1 - transfer_share) * visitor_share * min(0.10, 1 - capture)),
    ]
    sensitivity = [
        {"lever": lever, "test_change": step, "absolute_hotel_checkin_effect": float(guests),
         "absolute_guest_night_effect": float(guests * stay)}
        for lever, step, guests in steps
    ]
    sensitivity.append({"lever": "average_length_of_stay", "test_change": "+1 night",
                        "absolute_hotel_checkin_effect": 0.0,
                        "absolute_guest_night_effect": float(abs(delta_guests))})
    sensitivity.sort(key=lambda item: item["absolute_guest_night_effect"], reverse=True)

    return {
        "month": request.month,
        "departure_origin": {"country": request.departure_country, "city": request.departure_city},
        "model_run_id": bundle["manifest"]["run_id"],
        "baseline": {"hotel_checkins": baseline_guests, "estimated_guest_nights": baseline_nights},
        "scenario": {"hotel_checkins": baseline_guests + delta_guests, "estimated_guest_nights": baseline_nights + delta_guest_days},
        "change": {"hotel_checkins": delta_guests, "estimated_guest_nights": delta_guest_days},
        "chain_change": {
            "scheduled_seats": delta_seats,
            "arriving_passengers": delta_passengers,
            "point_to_point_passengers": delta_p2p,
            "estimated_inbound_visitors": delta_visitors,
            "estimated_hotel_checkins": delta_guests,
            "estimated_guest_nights": delta_guest_days,
        },
        "assumptions": {
            "weeks_in_month": weeks,
            "load_factor": load_factor,
            "transfer_transit_share": transfer_share,
            "nonresident_visitor_share": visitor_share,
            "hotel_capture_rate": capture,
            "average_length_of_stay_proxy": stay,
            "same_origin_nationality_share": local_share,
            "mapping_method": "assumed same-origin share plus historical hotel nationality shares",
        },
        "market_results": markets,
        "estimated_guest_nights_assumption_range": {
            "low": max(0, range_values[0]), "high": max(0, range_values[1]),
            "basis": "historical monthly hotel/P2P conversion p10–p90; widened for unseen origins",
            "excludes": "baseline forecast error and route-displacement uncertainty",
            "coverage_claim": "none",
        },
        "sensitivity": sensitivity,
        "warnings": warnings,
    }
