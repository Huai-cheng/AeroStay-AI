"""Build canonical hotel and aviation feature tables from supplied workbooks."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "artifacts" / "etl"


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


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.where(denominator.ne(0))
    return numerator.div(denominator)


def load_hotel() -> pd.DataFrame:
    domestic = normalize_columns(pd.read_excel(DATA / "data domestic_train.xlsx"))
    international = normalize_columns(pd.read_excel(DATA / "data international_train.xlsx"))
    domestic["segment"] = "Domestic"
    domestic["market"] = "DOMESTIC"
    international["segment"] = "International"
    international["market"] = international["nationality"].astype(str).str.upper().str.strip()
    columns = ["date", "guests", "new_arrivals", "same_day_guests", "segment", "market"]
    hotel = pd.concat([domestic[columns], international[columns]], ignore_index=True)
    hotel["date"] = pd.to_datetime(hotel["date"], errors="raise")
    for column in ("guests", "new_arrivals", "same_day_guests"):
        hotel[column] = pd.to_numeric(hotel[column], errors="coerce")
    hotel["same_day_guests_missing_indicator"] = hotel["same_day_guests"].isna().astype("int8")
    hotel["linear_time_trend_days"] = (hotel["date"] - hotel["date"].min()).dt.days
    hotel["weekend_indicator"] = hotel["date"].dt.dayofweek.isin([5, 6]).astype("int8")
    hotel["month_category"] = hotel["date"].dt.month.astype(str)
    hotel["day_of_week_category"] = hotel["date"].dt.dayofweek.astype(str)
    angle = 2.0 * math.pi * hotel["date"].dt.dayofyear / 365.25
    hotel["annual_seasonal_sine"] = np.sin(angle)
    hotel["annual_seasonal_cosine"] = np.cos(angle)

    hotel["previous_date"] = hotel["date"] - pd.DateOffset(years=1)
    history = hotel[
        ["date", "segment", "market", "guests", "new_arrivals", "same_day_guests"]
    ].rename(
        columns={
            "date": "previous_date",
            "guests": "previous_year_total_guests",
            "new_arrivals": "previous_year_new_arrivals",
            "same_day_guests": "previous_year_same_day_guests",
        }
    )
    hotel = hotel.merge(
        history,
        on=["previous_date", "segment", "market"],
        how="left",
        validate="many_to_one",
    )
    hotel["year_over_year_arrival_ratio"] = safe_ratio(
        hotel["new_arrivals"], hotel["previous_year_new_arrivals"].clip(lower=1.0)
    )
    return hotel.sort_values(["date", "segment", "market"]).reset_index(drop=True)


def load_flights() -> pd.DataFrame:
    flights = normalize_columns(pd.read_excel(DATA / "flight_data.xlsx"))
    flights["date"] = pd.to_datetime(flights["date"], errors="raise")
    flights["month"] = flights["date"].dt.to_period("M").dt.to_timestamp()
    flights["departure_country"] = (
        flights["departure_country_name"].astype(str).str.upper().str.strip()
    )
    route_columns = [
        "departure_country_name",
        "departure_city",
        "arrival_city",
        "airline_name",
        "destination",
    ]
    flights["route_key"] = flights[route_columns].fillna("UNKNOWN").astype(str).agg("|".join, axis=1)
    numeric = [
        "average_weekly_frequency",
        "total_seats",
        "total_pax",
        "total_p2p",
        "total_transfer",
        "total_transit",
    ]
    for column in numeric:
        flights[column] = pd.to_numeric(flights[column], errors="coerce")
    return flights


def build_route_monthly(flights: pd.DataFrame) -> pd.DataFrame:
    month_grain = (
        flights.groupby("month", observed=True)["date"]
        .nunique()
        .map(lambda count: "monthly_input" if count == 1 else "daily_input")
        .rename("source_period_grain")
    )
    route = flights.groupby(
        ["month", "departure_country", "route_key"], observed=True, as_index=False
    ).agg(
        average_weekly_flight_frequency=("average_weekly_frequency", "mean"),
        total_scheduled_seats=("total_seats", "sum"),
        total_passenger_movements=("total_pax", "sum"),
        total_point_to_point_passengers=("total_p2p", "sum"),
        total_transfer_passengers=("total_transfer", "sum"),
        total_transit_passengers=("total_transit", "sum"),
        observed_dates=("date", "nunique"),
    )
    first_month = route.groupby("route_key", observed=True)["month"].transform("min")
    last_month = route.groupby("route_key", observed=True)["month"].transform("max")
    route["new_route_indicator"] = route["month"].eq(first_month).astype("int8")
    # A route already present in the first observed month is left-censored: the
    # workbook cannot prove that it opened then, so do not label it as new.
    route.loc[route["month"].eq(route["month"].min()), "new_route_indicator"] = 0
    route["last_observed_route_month_indicator"] = route["month"].eq(last_month).astype("int8")
    return route.merge(month_grain, on="month", how="left", validate="many_to_one")


def build_origin_monthly(route: pd.DataFrame) -> pd.DataFrame:
    origin = route.groupby(["month", "departure_country"], observed=True, as_index=False).agg(
        total_scheduled_seats=("total_scheduled_seats", "sum"),
        total_passenger_movements=("total_passenger_movements", "sum"),
        total_point_to_point_passengers=("total_point_to_point_passengers", "sum"),
        total_transfer_passengers=("total_transfer_passengers", "sum"),
        total_transit_passengers=("total_transit_passengers", "sum"),
        active_route_count=("route_key", "nunique"),
        new_route_count=("new_route_indicator", "sum"),
    )
    # pandas sum normally turns an all-missing group into zero. That would
    # incorrectly describe the 2022 monthly source (where frequency is absent)
    # as having no flights. Preserve missingness until genuine frequency data
    # begins in 2023.
    frequency = (
        route.groupby(["month", "departure_country"], observed=True)[
            "average_weekly_flight_frequency"
        ]
        .sum(min_count=1)
        .rename("average_weekly_flight_frequency")
        .reset_index()
    )
    origin = origin.merge(
        frequency,
        on=["month", "departure_country"],
        how="left",
        validate="one_to_one",
    )
    final_month = route["month"].max()
    closures = (
        route.loc[route["last_observed_route_month_indicator"].eq(1), ["departure_country", "route_key", "month"]]
        .assign(month=lambda frame: frame["month"] + pd.offsets.MonthBegin(1))
    )
    closures = closures[closures["month"].le(final_month)]
    closure_counts = (
        closures.groupby(["month", "departure_country"], observed=True)["route_key"]
        .nunique()
        .rename("discontinued_route_count")
    )
    origin = origin.join(closure_counts, on=["month", "departure_country"])
    origin["discontinued_route_count"] = origin["discontinued_route_count"].fillna(0).astype(int)
    origin["passenger_load_factor"] = safe_ratio(
        origin["total_passenger_movements"], origin["total_scheduled_seats"]
    )
    origin["point_to_point_passenger_share"] = safe_ratio(
        origin["total_point_to_point_passengers"], origin["total_passenger_movements"]
    )
    origin["transfer_passenger_share"] = safe_ratio(
        origin["total_transfer_passengers"], origin["total_passenger_movements"]
    )
    origin["transit_passenger_share"] = safe_ratio(
        origin["total_transit_passengers"], origin["total_passenger_movements"]
    )
    monthly_seats = origin.groupby("month", observed=True)["total_scheduled_seats"].transform("sum")
    monthly_pax = origin.groupby("month", observed=True)["total_passenger_movements"].transform("sum")
    origin["departure_country_seat_share"] = safe_ratio(origin["total_scheduled_seats"], monthly_seats)
    origin["departure_country_passenger_share"] = safe_ratio(
        origin["total_passenger_movements"], monthly_pax
    )
    origin = origin.sort_values(["departure_country", "month"])
    prior_seats = origin.groupby("departure_country", observed=True)["total_scheduled_seats"].shift(12)
    prior_frequency = origin.groupby("departure_country", observed=True)[
        "average_weekly_flight_frequency"
    ].shift(12)
    origin["year_over_year_seat_change"] = safe_ratio(
        origin["total_scheduled_seats"] - prior_seats, prior_seats
    )
    origin["year_over_year_frequency_change"] = safe_ratio(
        origin["average_weekly_flight_frequency"] - prior_frequency, prior_frequency
    )
    return origin.reset_index(drop=True)


def build_global_monthly(origin: pd.DataFrame) -> pd.DataFrame:
    global_monthly = origin.groupby("month", observed=True, as_index=False).agg(
        total_scheduled_seats=("total_scheduled_seats", "sum"),
        total_passenger_movements=("total_passenger_movements", "sum"),
        total_point_to_point_passengers=("total_point_to_point_passengers", "sum"),
        total_transfer_passengers=("total_transfer_passengers", "sum"),
        total_transit_passengers=("total_transit_passengers", "sum"),
        active_route_count=("active_route_count", "sum"),
        new_route_count=("new_route_count", "sum"),
        discontinued_route_count=("discontinued_route_count", "sum"),
        departure_country_count=("departure_country", "nunique"),
    )
    frequency = (
        origin.groupby("month", observed=True)["average_weekly_flight_frequency"]
        .sum(min_count=1)
        .rename("average_weekly_flight_frequency")
        .reset_index()
    )
    global_monthly = global_monthly.merge(
        frequency, on="month", how="left", validate="one_to_one"
    )
    global_monthly["passenger_load_factor"] = safe_ratio(
        global_monthly["total_passenger_movements"], global_monthly["total_scheduled_seats"]
    )
    global_monthly["point_to_point_passenger_share"] = safe_ratio(
        global_monthly["total_point_to_point_passengers"],
        global_monthly["total_passenger_movements"],
    )
    global_monthly["transfer_passenger_share"] = safe_ratio(
        global_monthly["total_transfer_passengers"], global_monthly["total_passenger_movements"]
    )
    global_monthly["transit_passenger_share"] = safe_ratio(
        global_monthly["total_transit_passengers"], global_monthly["total_passenger_movements"]
    )
    concentration = (
        origin.assign(square_share=origin["departure_country_seat_share"].pow(2))
        .groupby("month", observed=True)["square_share"]
        .sum()
        .rename("origin_market_seat_concentration")
    )
    global_monthly = global_monthly.merge(
        concentration, on="month", how="left", validate="one_to_one"
    ).sort_values("month")
    prior_seats = global_monthly["total_scheduled_seats"].shift(12)
    prior_frequency = global_monthly["average_weekly_flight_frequency"].shift(12)
    global_monthly["year_over_year_seat_change"] = safe_ratio(
        global_monthly["total_scheduled_seats"] - prior_seats, prior_seats
    )
    global_monthly["year_over_year_frequency_change"] = safe_ratio(
        global_monthly["average_weekly_flight_frequency"] - prior_frequency,
        prior_frequency,
    )
    return global_monthly.reset_index(drop=True)


def validate_flight_identity(flights: pd.DataFrame) -> None:
    components = flights[["total_p2p", "total_transfer", "total_transit"]].sum(axis=1)
    complete = flights[["total_pax", "total_p2p", "total_transfer", "total_transit"]].notna().all(axis=1)
    if not np.allclose(
        flights.loc[complete, "total_pax"], components.loc[complete], rtol=1e-7, atol=1e-7
    ):
        raise ValueError("Passenger identity failed: total is not point-to-point + transfer + transit")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hotel = load_hotel()
    flights = load_flights()
    validate_flight_identity(flights)
    route = build_route_monthly(flights)
    origin = build_origin_monthly(route)
    global_monthly = build_global_monthly(origin)

    hotel.to_csv(OUTPUT / "hotel_daily.csv", index=False)
    route.to_csv(OUTPUT / "route_monthly.csv", index=False)
    origin.to_csv(OUTPUT / "flight_origin_monthly.csv", index=False)
    global_monthly.to_csv(OUTPUT / "flight_global_monthly.csv", index=False)
    print(f"Wrote ETL tables to {OUTPUT}")
    print(
        {
            "hotel_daily_rows": len(hotel),
            "route_monthly_rows": len(route),
            "flight_origin_monthly_rows": len(origin),
            "flight_global_monthly_rows": len(global_monthly),
        }
    )


if __name__ == "__main__":
    main()
