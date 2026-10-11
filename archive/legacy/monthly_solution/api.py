"""HTTP access to the trained model and scenario simulator."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dtc.config import load_config
from dtc.model import baseline_predictions, load_serving_bundle
from dtc.scenario import ScenarioRequest, simulate


app = FastAPI(title="Abu Dhabi air-to-hotel simulator", version="0.1.0")


class PredictionRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


def _config():
    return load_config(os.environ.get("DTC_CONFIG", "config/project.yaml"))


@app.get("/health")
def health():
    try:
        bundle = load_serving_bundle(_config())
        return {"status": "ready", "run_id": bundle["manifest"]["run_id"]}
    except (FileNotFoundError, ValueError) as error:
        return {"status": "no_model", "detail": str(error)}


@app.get("/v1/model")
def model_info():
    try:
        bundle = load_serving_bundle(_config())
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    summary_path = Path(bundle["run_dir"]) / "metrics" / "summary.json"
    return {
        "manifest": bundle["manifest"],
        "holdout_metrics": json.loads(summary_path.read_text(encoding="utf-8")),
        "reference_note": bundle["reference"]["rate_note"],
    }


@app.post("/v1/predict")
def predict(request: PredictionRequest):
    try:
        config = _config()
        bundle = load_serving_bundle(config)
        rows = baseline_predictions(config, bundle, request.month)
    except (FileNotFoundError, ValueError) as error:
        status_code = 503 if isinstance(error, FileNotFoundError) else 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    markets = [
        {"guest_nationality": str(row.nationality),
         "hotel_checkins": float(row.predicted_arrivals),
         "estimated_guest_nights": float(row.predicted_guest_days)}
        for row in rows.itertuples()
    ]
    return {
        "month": request.month,
        "model_run_id": bundle["manifest"]["run_id"],
        "hotel_checkins": float(rows["predicted_arrivals"].sum()),
        "estimated_guest_nights": float(rows["predicted_guest_days"].sum()),
        "markets": markets,
        "night_definition": "Estimated from guest-day/arrival stay proxy; direct overnight guest nights not supplied",
    }


@app.post("/v1/scenarios/simulate")
def simulate_scenario(request: ScenarioRequest):
    try:
        config = _config()
        bundle = load_serving_bundle(config)
        return simulate(config, bundle, request)
    except (FileNotFoundError, ValueError) as error:
        status_code = 503 if isinstance(error, FileNotFoundError) else 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error
