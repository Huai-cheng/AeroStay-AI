"""Download licensed workbooks and the trained model from private Vercel Blob.

Runs as the Vercel build command. The competition data and model binary are
never committed (see data/README.md), so deployments pull them from a private
Blob store into the same `data/` and `artifacts/selected_model/` paths that a
local run uses.

It also writes the application-state snapshot that the API loads when
AEROSTAY_USE_STATE_SNAPSHOT=1, so cold starts skip workbook parsing.

Upload or refresh the files with `vercel blob put <file> --access private
--pathname aerostay/data/<name>` (or `aerostay/selected_model/<name>`).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
BLOB_PREFIX = "aerostay"

ASSETS = {
    "data/flight_data.xlsx": ROOT / "data" / "flight_data.xlsx",
    "data/data international_train.xlsx": ROOT / "data" / "data international_train.xlsx",
    "data/data international_test.xlsx": ROOT / "data" / "data international_test.xlsx",
    "data/data domestic_train.xlsx": ROOT / "data" / "data domestic_train.xlsx",
    "data/data domestic_test.xlsx": ROOT / "data" / "data domestic_test.xlsx",
    "selected_model/pooled_poisson_xgboost.joblib": ROOT / "artifacts" / "selected_model" / "pooled_poisson_xgboost.joblib",
    "selected_model/model_metadata.json": ROOT / "artifacts" / "selected_model" / "model_metadata.json",
    "selected_model/holdout_metrics.json": ROOT / "artifacts" / "selected_model" / "holdout_metrics.json",
}


def store_base_url(token: str) -> str:
    override = os.environ.get("AEROSTAY_BLOB_BASE_URL")
    if override:
        return override.rstrip("/")
    # Read-write tokens look like vercel_blob_rw_<storeId>_<secret>.
    store_id = token.split("_")[3].lower()
    return f"https://{store_id}.private.blob.vercel-storage.com"


def main() -> None:
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise SystemExit("BLOB_READ_WRITE_TOKEN is not set; connect the private Blob store to this project.")
    base = store_base_url(token)
    headers = {"Authorization": f"Bearer {token}"}
    for pathname, destination in ASSETS.items():
        url = f"{base}/{BLOB_PREFIX}/{quote(pathname)}"
        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)
        print(f"fetched {pathname} ({len(response.content):,} bytes)")

    # Imported here so the downloads above land before pipeline paths are read.
    from prototype.service import STATE_SNAPSHOT, write_state_snapshot

    write_state_snapshot()
    print(f"wrote {STATE_SNAPSHOT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
