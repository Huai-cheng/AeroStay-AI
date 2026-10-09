"""Configuration loading and path resolution."""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path("config/project.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("Config must be a mapping with version: 1")
    required = ("data", "split", "targets", "model", "market_mapping", "assumptions", "artifacts", "service")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(missing)}")
    config = copy.deepcopy(config)
    # The repo root is the parent of config/, independent of the caller's cwd.
    root = config_path.parent.parent
    config["_config_path"] = str(config_path)
    config["_root"] = str(root)
    for section, keys in {"data": ("raw_dir", "processed_dir"), "artifacts": ("runs_dir", "selected_model_file")}.items():
        for key in keys:
            value = Path(config[section][key])
            config[section][key] = str(value if value.is_absolute() else root / value)
    for key in ("international_train_file", "international_test_file", "domestic_train_file", "domestic_test_file", "flight_file", "dictionary_file"):
        if not config["data"].get(key):
            raise ValueError(f"Missing data.{key}")
    for key in ("nonresident_visitor_share", "same_origin_nationality_share"):
        value = config["assumptions"].get(key)
        if value is None or not 0 <= float(value) <= 1:
            raise ValueError(f"assumptions.{key} must be between 0 and 1")
    split = config["split"]
    dates = {key: date.fromisoformat(str(split[key])) for key in
             ("train_end", "validation_start", "validation_end", "official_test_start", "official_test_end")}
    if not dates["train_end"] < dates["validation_start"] <= dates["validation_end"] < dates["official_test_start"] <= dates["official_test_end"]:
        raise ValueError("Split dates must be ordered: training, validation, official test")
    model = config["model"]
    if not model.get("air_elasticity_candidates") or any(
        not 0 <= float(value) <= 1 for value in model["air_elasticity_candidates"]
    ):
        raise ValueError("model.air_elasticity_candidates must contain values between 0 and 1")
    if float(model["seat_smoothing"]) < 0:
        raise ValueError("model.seat_smoothing cannot be negative")
    lower, upper = (float(value) for value in model["capacity_ratio_clip"])
    if not 0 < lower <= upper:
        raise ValueError("model.capacity_ratio_clip must be positive and ascending")
    for key in ("api_port", "web_port"):
        if not 1 <= int(config["service"][key]) <= 65535:
            raise ValueError(f"service.{key} must be a valid TCP port")
    return config


def raw_path(config: dict[str, Any], key: str) -> Path:
    return Path(config["data"]["raw_dir"]) / config["data"][key]


def processed_path(config: dict[str, Any], name: str) -> Path:
    return Path(config["data"]["processed_dir"]) / name
