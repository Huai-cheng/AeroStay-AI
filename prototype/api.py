"""FastAPI boundary for the DCT scenario and model service."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from prototype.service import application_state, global_sensitivity, options_payload, sensitivity, simulate


class ScenarioRequest(BaseModel):
    mode: Literal["Existing route", "New route"] = "Existing route"
    origin_country: str
    target_nationality: str
    start_date: date
    end_date: date
    scenario_weekly_flights: float | None = Field(default=None, ge=0, le=1000)
    frequency_change_pct: float = Field(default=0, ge=-100, le=300)
    seats_per_flight_change_pct: float = Field(default=0, ge=-80, le=200)
    load_factor_change_points: float = Field(default=0, ge=-50, le=50)
    transfer_share: float | None = Field(default=None, ge=0, le=0.95)
    transit_share: float | None = Field(default=None, ge=0, le=0.50)
    visitor_share: float = Field(default=0.75, ge=0, le=1)
    hotel_capture_rate: float = Field(default=0.65, ge=0, le=1)
    nationality_allocation_share: float = Field(default=1.0, ge=0, le=1)
    new_route_weekly_flights: float = Field(default=2, ge=0, le=100)
    new_route_seats_per_flight: float = Field(default=180, ge=20, le=1000)
    new_route_load_factor: float = Field(default=0.75, ge=0, le=1.25)

    @model_validator(mode="after")
    def validate_scenario(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.transfer_share is not None and self.transit_share is not None and self.transfer_share + self.transit_share >= 0.98:
            raise ValueError("transfer_share plus transit_share must be less than 0.98")
        return self


app = FastAPI(
    title="DCT Flight-to-Hotel API",
    version="1.0.0",
    description="Shared pooled Poisson XGBoost and transparent scenario service.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dct-flight-hotel"}


@app.get("/model/metrics")
def model_metrics() -> dict:
    state = application_state()
    return {"metadata": state["metadata"], "metrics": state["metrics"]}


@app.get("/options")
def options() -> dict:
    return options_payload()


@app.post("/simulate")
def run_simulation(request: ScenarioRequest) -> dict:
    try:
        return simulate(request.model_dump(mode="json"))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/sensitivity")
def run_sensitivity(request: ScenarioRequest) -> dict:
    try:
        return sensitivity(request.model_dump(mode="json"))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/global-sensitivity")
def run_global_sensitivity(request: ScenarioRequest) -> dict:
    try:
        return global_sensitivity(request.model_dump(mode="json"))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
