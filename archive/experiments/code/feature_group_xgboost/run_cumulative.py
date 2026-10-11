"""Combine validation-positive feature groups and finalize sequential history."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_experiments as exp


OUTPUT = exp.OUTPUT


def parse_features(value: str | float) -> list[str]:
    if pd.isna(value) or not str(value):
        return []
    return str(value).split("|")


def append_csv(path: Path, rows: list[dict]) -> None:
    existing = pd.read_csv(path) if path.exists() else pd.DataFrame()
    pd.concat([existing, pd.DataFrame(rows)], ignore_index=True).to_csv(path, index=False)


def markdown_table(records: list[dict]) -> list[str]:
    columns = ["selection", "rows", "wmape", "bias_pct", "mae", "rmse", "r2"]
    lines = [
        "| Selection | Rows | WMAPE | Bias | MAE | RMSE | R-squared |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in records:
        lines.append(
            f"| {record['selection']} | {int(record['rows'])} | {record['wmape']:.2%} | "
            f"{record['bias_pct']:.2%} | {record['mae']:.2f} | {record['rmse']:.2f} | "
            f"{record['r2']:.4f} |"
        )
    return lines


def production_eligible(experiment: str, scope: str) -> bool:
    # E3 uses realized passenger composition. E4 includes an experimental
    # origin-to-nationality exact-match bridge and realized passenger share.
    if "E3" in experiment:
        return False
    # For domestic rows the origin-matched columns are entirely missing and
    # therefore constant after preprocessing. E4's only effective signal is
    # global scheduled-seat concentration, which is available in advance.
    if "E4" in experiment and scope != "domestic":
        return False
    return True


def main() -> None:
    history_path = OUTPUT / "experiment_history.csv"
    history = pd.read_csv(history_path)
    if history["mode"].eq("cumulative").any():
        old_cumulative_ids = set(history.loc[history["mode"].eq("cumulative"), "run_id"])
        history = history[~history["mode"].eq("cumulative")].copy()
        history.to_csv(history_path, index=False)
        for name in ("market_metrics.csv", "monthly_metrics.csv"):
            path = OUTPUT / name
            if path.exists():
                prior = pd.read_csv(path)
                prior = prior[~prior["run_id"].isin(old_cumulative_ids)]
                prior.to_csv(path, index=False)
    isolated = history[history["status"].eq("ok") & history["mode"].eq("isolated")].copy()
    frame = exp.load_model_frame()
    new_history: list[dict] = []
    new_market: list[dict] = []
    new_month: list[dict] = []
    next_run = int(history["run_id"].str.removeprefix("R").astype(int).max()) + 1

    for scope in exp.SCOPES:
        tune, validation, offline = exp.split(frame, scope)
        categorical = exp.BASE_CATEGORICAL + (["segment"] if scope == "pooled" else [])
        for loss in exp.LOSSES:
            subset = isolated[(isolated["scope"].eq(scope)) & (isolated["loss"].eq(loss))]
            baseline = float(
                subset.loc[subset["experiment"].eq("E0_baseline"), "validation_wmape"].iloc[0]
            )
            accepted = subset[
                ~subset["experiment"].eq("E0_baseline")
                & subset["validation_wmape"].lt(baseline)
            ].sort_values("experiment")
            additions: list[str] = []
            accepted_names: list[str] = []
            for row in accepted.itertuples():
                accepted_names.append(row.experiment)
                for feature in parse_features(row.added_features):
                    if feature not in additions:
                        additions.append(feature)
            if not additions:
                continue

            run_id = f"R{next_run:03d}"
            next_run += 1
            experiment = "E6_combined__" + "+".join(name.split("_", 1)[0] for name in accepted_names)
            numeric = exp.BASE_NUMERIC + additions
            started = time.perf_counter()
            record = {
                "run_id": run_id,
                "scope": scope,
                "mode": "cumulative",
                "experiment": experiment,
                "loss": loss,
                "added_features": "|".join(additions),
                "numeric_features": "|".join(numeric),
                "categorical_features": "|".join(categorical),
                "accepted_isolated_groups": "|".join(accepted_names),
                "tune_end": str(exp.TUNE_END.date()),
                "validation_start": str(exp.VALIDATION_START.date()),
                "validation_end": str(exp.VALIDATION_END.date()),
                "offline_start": str(exp.OFFLINE_START.date()),
                "offline_end": str(exp.OFFLINE_END.date()),
                "random_state": exp.RANDOM_STATE,
                "production_eligible": production_eligible(experiment, scope),
            }
            try:
                validation_prediction, offline_prediction, best_trees, bin_count = exp.fit_predict(
                    tune, validation, offline, numeric, categorical, loss
                )
                validation_metrics = exp.metrics(validation, validation_prediction)
                offline_metrics = exp.metrics(offline, offline_prediction)
                record.update({f"validation_{key}": value for key, value in validation_metrics.items()})
                record.update({f"offline_{key}": value for key, value in offline_metrics.items()})
                record.update(
                    {
                        "best_trees": best_trees,
                        "bin_count": bin_count,
                        "status": "ok",
                        "seconds": round(time.perf_counter() - started, 3),
                    }
                )
                markets, months = exp.breakdowns(
                    offline, offline_prediction, run_id, scope, experiment, loss
                )
                new_market.extend(markets)
                new_month.extend(months)
                prediction_output = offline[["date", "segment", "market", "guests"]].copy()
                prediction_output["prediction"] = offline_prediction
                prediction_output.to_csv(OUTPUT / f"predictions__{run_id}.csv", index=False)
                print(
                    f"{run_id} {scope} {loss} {experiment}: "
                    f"val={validation_metrics['wmape']:.4%} offline={offline_metrics['wmape']:.4%}",
                    flush=True,
                )
            except Exception as exc:
                record.update(
                    {
                        "status": "failed",
                        "error": repr(exc),
                        "seconds": round(time.perf_counter() - started, 3),
                    }
                )
                print(f"{run_id} FAILED: {exc!r}", flush=True)
            new_history.append(record)

    append_csv(history_path, new_history)
    append_csv(OUTPUT / "market_metrics.csv", new_market)
    append_csv(OUTPUT / "monthly_metrics.csv", new_month)

    complete = pd.read_csv(history_path)
    ok = complete[complete["status"].eq("ok")].copy()
    ok["production_eligible"] = ok.apply(
        lambda row: bool(row.get("production_eligible", False))
        if row["mode"] == "cumulative"
        else production_eligible(str(row["experiment"]), str(row["scope"])),
        axis=1,
    )
    best_accuracy = ok.sort_values("validation_wmape").groupby("scope", observed=True).head(1)
    best_eligible = (
        ok[ok["production_eligible"]]
        .sort_values("validation_wmape")
        .groupby("scope", observed=True)
        .head(1)
    )

    selected_predictions: dict[str, pd.DataFrame] = {}
    for selection_name, selection in (("accuracy", best_accuracy), ("eligible", best_eligible)):
        for row in selection.itertuples():
            tune, validation, offline = exp.split(frame, row.scope)
            numeric = parse_features(row.numeric_features)
            categorical = parse_features(row.categorical_features)
            _, offline_prediction, _, _ = exp.fit_predict(
                tune, validation, offline, numeric, categorical, row.loss
            )
            output = offline[["date", "segment", "market", "guests"]].copy()
            output["prediction"] = offline_prediction
            output["selected_run_id"] = row.run_id
            output.to_csv(OUTPUT / f"selected_{selection_name}__{row.scope}.csv", index=False)
            selected_predictions[f"{selection_name}_{row.scope}"] = output

    combined_records = []
    for selection_name in ("accuracy", "eligible"):
        domestic = selected_predictions[f"{selection_name}_domestic"]
        international = selected_predictions[f"{selection_name}_international"]
        combined = pd.concat([domestic, international], ignore_index=True)
        combined_metrics = exp.metrics(combined, combined["prediction"].to_numpy())
        combined_records.append({"selection": selection_name, **combined_metrics})
    pd.DataFrame(combined_records).to_csv(OUTPUT / "selected_two_head_metrics.csv", index=False)

    report = [
        "# Final feature-group experiment report",
        "",
        "Model and feature selection below uses validation WMAPE; the offline period is reported but not used for selection.",
        "",
        "## Validation-selected accuracy winner",
        "",
        "| Scope | Run | Experiment | Loss | Validation WMAPE | Offline WMAPE | Production eligible |",
        "| --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in best_accuracy.itertuples():
        report.append(
            f"| {row.scope} | {row.run_id} | {row.experiment} | {row.loss} | "
            f"{row.validation_wmape:.2%} | {row.offline_wmape:.2%} | {bool(row.production_eligible)} |"
        )
    report.extend(
        [
            "",
            "## Validation-selected production-eligible winner",
            "",
            "| Scope | Run | Experiment | Loss | Validation WMAPE | Offline WMAPE |",
            "| --- | --- | --- | --- | ---: | ---: |",
        ]
    )
    for row in best_eligible.itertuples():
        report.append(
            f"| {row.scope} | {row.run_id} | {row.experiment} | {row.loss} | "
            f"{row.validation_wmape:.2%} | {row.offline_wmape:.2%} |"
        )
    report.extend(["", "## Selected two-head combined metrics", ""])
    report.extend(markdown_table(combined_records))
    report.extend(
        [
            "",
            "Production eligibility excludes experiments containing historically realized passenger composition or the provisional exact origin-to-nationality bridge.",
            "",
        ]
    )
    (OUTPUT / "FINAL_EXPERIMENT_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    metadata = {
        "isolated_runs": int(complete["mode"].eq("isolated").sum()),
        "cumulative_runs": int(complete["mode"].eq("cumulative").sum()),
        "failed_runs": int(complete["status"].ne("ok").sum()),
        "accuracy_selection": best_accuracy[
            ["scope", "run_id", "experiment", "loss", "validation_wmape", "offline_wmape"]
        ].to_dict(orient="records"),
        "eligible_selection": best_eligible[
            ["scope", "run_id", "experiment", "loss", "validation_wmape", "offline_wmape"]
        ].to_dict(orient="records"),
    }
    (OUTPUT / "final_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("\n", pd.DataFrame(combined_records).to_string(index=False))


if __name__ == "__main__":
    main()
