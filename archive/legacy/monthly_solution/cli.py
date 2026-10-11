"""Terminal interface for auditable pipeline stages and local simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from dtc.config import load_config
from dtc.data import build_features, map_markets, prepare, write_audit, write_split
from dtc.model import baseline_predictions, evaluate, load_serving_bundle, package, predict_official, train
from dtc.scenario import ScenarioRequest, simulate


def main() -> None:
    parser = argparse.ArgumentParser(description="Abu Dhabi air-to-hotel simulator")
    parser.add_argument("command", choices=["audit", "prepare", "map-markets", "features", "split", "train", "evaluate", "package", "predict", "predict-official", "simulate", "serve"])
    parser.add_argument("--config", default="config/project.yaml", help="Path to YAML configuration")
    parser.add_argument("--run-id", help="Run ID for evaluate/package/simulate")
    parser.add_argument("--request", help="Scenario JSON file for simulate")
    parser.add_argument("--month", help="YYYY-MM for predict")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command == "audit":
            result = write_audit(config)
        elif args.command == "prepare":
            result = prepare(config)
        elif args.command == "map-markets":
            result = map_markets(config)
        elif args.command == "features":
            result = build_features(config)
        elif args.command == "split":
            result = write_split(config)
        elif args.command == "train":
            run_id, run_dir = train(config)
            result = {"run_id": run_id, "run_dir": str(run_dir)}
        elif args.command == "evaluate":
            if not args.run_id:
                parser.error("evaluate requires --run-id")
            result = evaluate(config, args.run_id)
        elif args.command == "package":
            if not args.run_id:
                parser.error("package requires --run-id")
            result = package(config, args.run_id)
        elif args.command == "simulate":
            if not args.request:
                parser.error("simulate requires --request scenario.json")
            request = ScenarioRequest.model_validate_json(Path(args.request).read_text(encoding="utf-8"))
            result = simulate(config, load_serving_bundle(config, args.run_id), request)
        elif args.command == "predict":
            if not args.month:
                parser.error("predict requires --month YYYY-MM")
            rows = baseline_predictions(config, load_serving_bundle(config, args.run_id), args.month)
            result = {"month": args.month, "hotel_checkins": float(rows["predicted_arrivals"].sum()),
                      "estimated_guest_nights": float(rows["predicted_guest_days"].sum()),
                      "markets": rows[["nationality", "predicted_arrivals", "predicted_guest_days"]].to_dict("records")}
        elif args.command == "predict-official":
            result = predict_official(config, args.run_id)
        else:
            uvicorn.run("dtc.api:app", host=config["service"]["api_host"], port=int(config["service"]["api_port"]))
            return
        print(json.dumps(result, indent=2, default=str))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
