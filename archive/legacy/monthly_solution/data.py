"""Read-only source ingestion and reproducible monthly feature preparation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dtc.config import processed_path, raw_path


def _month(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="raise").dt.to_period("M").dt.to_timestamp()


def _name(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper().str.replace(r"\s+", " ", regex=True)


def _read_excel(config: dict[str, Any], key: str) -> pd.DataFrame:
    path = raw_path(config, key)
    if not path.is_file():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_excel(path, sheet_name="Export", engine="openpyxl")


def audit(config: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {"files": {}, "checks": {}}
    for key in ("flight_file", "international_train_file", "international_test_file", "domestic_train_file", "domestic_test_file"):
        frame = _read_excel(config, key)
        dates = pd.to_datetime(frame["Date"])
        report["files"][key] = {
            "path": str(raw_path(config, key)),
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "first_date": dates.min().date().isoformat(),
            "last_date": dates.max().date().isoformat(),
            "unique_dates": int(dates.nunique()),
            "missing_by_column": {str(k): int(v) for k, v in frame.isna().sum().items() if v},
        }
        if key == "flight_file":
            for col in ("Total PAX", "Total Transfer", "Total Transit", "Total P2P", "Total Seats"):
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
            difference = frame["Total PAX"] - frame["Total Transfer"] - frame["Total Transit"] - frame["Total P2P"]
            report["checks"]["p2p_identity_mismatch_rows"] = int(difference.fillna(0).ne(0).sum())
            report["checks"]["flight_dates_per_month_2022"] = (
                dates[dates.dt.year.eq(2022)].groupby(dates.dt.to_period("M")).nunique().astype(int).to_dict()
            )
            report["checks"]["flight_dates_per_month_2022"] = {
                str(k): v for k, v in report["checks"]["flight_dates_per_month_2022"].items()
            }
    report["checks"]["dictionary_present"] = raw_path(config, "dictionary_file").is_file()
    return report


def prepare(config: dict[str, Any]) -> dict[str, Path]:
    out_dir = Path(config["data"]["processed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    flights = _read_excel(config, "flight_file")
    flights["month"] = _month(flights["Date"])
    flights["departure_country"] = _name(flights["Departure Country Name"])
    flight_map = {
        "Total Seats": "seats",
        "Total PAX": "passengers",
        "Total Transfer": "transfers",
        "Total Transit": "transit",
        "Total P2P": "p2p",
    }
    for source in flight_map:
        flights[source] = pd.to_numeric(flights[source], errors="coerce")
    air = flights.groupby(["month", "departure_country"], dropna=False)[list(flight_map)].sum(min_count=1).reset_index()
    air = air.rename(columns=flight_map).sort_values(["month", "departure_country"])
    air["load_factor_observed"] = air["passengers"] / air["seats"].replace(0, np.nan)
    air["transfer_transit_share_observed"] = (air["transfers"] + air["transit"]) / air["passengers"].replace(0, np.nan)
    air_path = out_dir / "air_origin_month.csv"
    air.to_csv(air_path, index=False)

    hotel_parts = []
    for key, split_name in (("international_train_file", "train"), ("international_test_file", "official_test")):
        hotel = _read_excel(config, key)
        hotel["month"] = _month(hotel["Date"])
        hotel["nationality"] = _name(hotel["Nationality"])
        hotel["new_arrivals"] = pd.to_numeric(hotel["New Arrivals"], errors="coerce")
        hotel["guests"] = pd.to_numeric(hotel["Guests"], errors="coerce") if "Guests" in hotel else np.nan
        grouped = hotel.groupby(["month", "nationality"], dropna=False).agg(
            hotel_new_arrivals=("new_arrivals", "sum"),
            guest_days=("guests", "sum"),
            missing_new_arrivals=("new_arrivals", lambda x: int(x.isna().sum())),
            observed_days=("Date", "nunique"),
        ).reset_index()
        grouped["split"] = split_name
        if split_name == "official_test":
            grouped["guest_days"] = np.nan
        hotel_parts.append(grouped)
    hotel_monthly = pd.concat(hotel_parts, ignore_index=True).sort_values(["month", "nationality"])
    hotel_path = out_dir / "hotel_nationality_month.csv"
    hotel_monthly.to_csv(hotel_path, index=False)

    domestic_parts = []
    for key, split_name in (("domestic_train_file", "train"), ("domestic_test_file", "official_test")):
        domestic = _read_excel(config, key)
        domestic["month"] = _month(domestic["Date"])
        domestic["new_arrivals"] = pd.to_numeric(domestic["New Arrivals"], errors="coerce")
        domestic["guests"] = pd.to_numeric(domestic["Guests"], errors="coerce") if "Guests" in domestic else np.nan
        grouped = domestic.groupby("month").agg(
            hotel_new_arrivals=("new_arrivals", "sum"), guest_days=("guests", "sum")
        ).reset_index()
        grouped["split"] = split_name
        if split_name == "official_test":
            grouped["guest_days"] = np.nan
        domestic_parts.append(grouped)
    domestic_path = out_dir / "domestic_month.csv"
    pd.concat(domestic_parts, ignore_index=True).to_csv(domestic_path, index=False)

    return {"air": air_path, "hotel": hotel_path, "domestic": domestic_path}


def build_features(config: dict[str, Any]) -> Path:
    air = pd.read_csv(processed_path(config, "air_origin_month.csv"), parse_dates=["month"])
    hotel = pd.read_csv(processed_path(config, "hotel_nationality_month.csv"), parse_dates=["month"])
    mapping = pd.read_csv(processed_path(config, "market_allocation_assumption.csv"))
    allocated = air[["month", "departure_country", "seats"]].merge(mapping, how="left", on="departure_country")
    allocated["allocated_origin_seats"] = allocated["seats"] * allocated["allocation_share"]
    allocated = allocated.groupby(["month", "guest_nationality"], as_index=False)["allocated_origin_seats"].sum()
    allocated = allocated.rename(columns={"guest_nationality": "nationality"})
    air = air.rename(columns={"departure_country": "nationality", "seats": "direct_origin_seats"})
    direct = air[["month", "nationality", "direct_origin_seats"]]
    citywide = air.groupby("month", as_index=False)["direct_origin_seats"].sum().rename(
        columns={"direct_origin_seats": "citywide_seats"}
    )
    features = (hotel.merge(direct, how="left", on=["month", "nationality"])
               .merge(citywide, how="left", on="month")
               .merge(allocated, how="left", on=["month", "nationality"]))
    features["direct_origin_seats"] = features["direct_origin_seats"].fillna(0)
    features["allocated_origin_seats"] = features["allocated_origin_seats"].fillna(0)
    features["month_number"] = features["month"].dt.month
    features["year_index"] = features["month"].dt.year - 2022
    prior = hotel.loc[hotel["split"].eq("train"), ["month", "nationality", "hotel_new_arrivals"]].copy()
    prior["month"] = prior["month"] + pd.DateOffset(years=1)
    prior = prior.rename(columns={"hotel_new_arrivals": "arrivals_same_month_last_year"})
    features = features.merge(prior, how="left", on=["month", "nationality"])
    features["lag12_missing"] = features["arrivals_same_month_last_year"].isna().astype(int)
    prior_air = features[["month", "nationality", "allocated_origin_seats"]].copy()
    prior_air["month"] = prior_air["month"] + pd.DateOffset(years=1)
    prior_air = prior_air.rename(columns={"allocated_origin_seats": "allocated_seats_same_month_last_year"})
    features = features.merge(prior_air, how="left", on=["month", "nationality"])
    # Hidden official-test labels are never exposed as supervised targets.
    features.loc[features["split"].eq("official_test"), ["hotel_new_arrivals", "guest_days"]] = np.nan
    feature_path = processed_path(config, "market_month_features.csv")
    features.to_csv(feature_path, index=False)
    return feature_path


def write_audit(config: dict[str, Any]) -> Path:
    path = processed_path(config, "data_quality.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit(config), indent=2), encoding="utf-8")
    return path


def map_markets(config: dict[str, Any]) -> Path:
    """Materialize the explicit, assumption-based scenario allocation table.

    It is a scenario assumption, not an inferred passenger-nationality crosswalk.
    """
    air = pd.read_csv(processed_path(config, "air_origin_month.csv"), parse_dates=["month"])
    hotel = pd.read_csv(processed_path(config, "hotel_nationality_month.csv"), parse_dates=["month"])
    cutoff = pd.Timestamp(config["split"]["train_end"])
    history = hotel.loc[hotel["split"].eq("train") & hotel["month"].le(cutoff)]
    # Uniform non-local shares avoid using future target magnitudes in model features.
    nationalities = sorted(history["nationality"].dropna().unique())
    shares = {market: 1 / len(nationalities) for market in nationalities}
    local_share = float(config["assumptions"]["same_origin_nationality_share"])
    records = []
    for origin in sorted(air["departure_country"].dropna().unique()):
        for nationality, historical_share in shares.items():
            fraction = (1 - local_share) * historical_share + (local_share if nationality == origin else 0)
            if fraction > 0:
                records.append({"departure_country": origin, "guest_nationality": nationality,
                                "allocation_share": fraction, "method": "assumed same-origin share + uniform non-local allocation"})
        if origin not in shares:
            records.append({"departure_country": origin, "guest_nationality": "OTHER_UNKNOWN",
                            "allocation_share": local_share, "method": "unmatched departure origin"})
    mapping = pd.DataFrame(records)
    totals = mapping.groupby("departure_country")["allocation_share"].sum()
    if not np.allclose(totals.to_numpy(), 1.0):
        raise ValueError("Origin-to-nationality allocation shares do not sum to one")
    path = processed_path(config, "market_allocation_assumption.csv")
    mapping.to_csv(path, index=False)
    return path


def write_split(config: dict[str, Any]) -> Path:
    frame = pd.read_csv(processed_path(config, "market_month_features.csv"), parse_dates=["month"])
    train_end = pd.Timestamp(config["split"]["train_end"])
    validation_start = pd.Timestamp(config["split"]["validation_start"])
    validation_end = pd.Timestamp(config["split"]["validation_end"])
    clean = frame["missing_new_arrivals"].eq(0)
    frame.loc[frame["split"].eq("train") & frame["month"].le(train_end) & clean].to_csv(
        processed_path(config, "train_features.csv"), index=False
    )
    frame.loc[frame["split"].eq("train") & frame["month"].between(validation_start, validation_end) & clean].to_csv(
        processed_path(config, "validation_features.csv"), index=False
    )
    frame.loc[frame["split"].eq("official_test")].to_csv(
        processed_path(config, "official_test_features.csv"), index=False
    )
    manifest = {
        "training_rows": int((frame["split"].eq("train") & frame["month"].le(train_end) & clean).sum()),
        "validation_rows": int((frame["split"].eq("train") & frame["month"].between(validation_start, validation_end) & clean).sum()),
        "official_test_rows": int(frame["split"].eq("official_test").sum()),
        "train_end": train_end.date().isoformat(),
        "validation_period": [validation_start.date().isoformat(), validation_end.date().isoformat()],
        "official_test_has_guest_labels": False,
    }
    path = processed_path(config, "split_manifest.json")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
