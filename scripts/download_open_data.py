from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"


def headers() -> dict[str, str]:
    h = {"User-Agent": "homewise-sg-downloader/0.1"}
    if os.getenv("DATA_GOV_API_KEY"):
        h["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return h


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def download_datastore(dataset_id: str, out_path: Path, limit: int = 5000, max_records: int | None = None) -> int:
    rows, offset = [], 0
    while True:
        page_limit = limit if max_records is None else min(limit, max_records - len(rows))
        if page_limit <= 0:
            break
        r = requests.get(DATASTORE_URL, params={"resource_id": dataset_id, "limit": page_limit, "offset": offset}, headers=headers(), timeout=60)
        r.raise_for_status()
        result = r.json().get("result", {})
        page = result.get("records", [])
        rows.extend(page)
        offset += len(page)
        if not page or offset >= int(result.get("total", offset)):
            break
    pd.DataFrame(rows).drop(columns=["_id"], errors="ignore").to_csv(out_path, index=False)
    return len(rows)


def download_poll_file(dataset_id: str, out_path: Path) -> None:
    poll = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=headers(), timeout=60)
    poll.raise_for_status()
    download_url = poll.json()["data"]["url"]
    data = requests.get(download_url, headers=headers(), timeout=120)
    data.raise_for_status()
    out_path.write_bytes(data.content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download HomeWise SG open data sources")
    parser.add_argument("--manifest", default="config/data_sources.yml")
    parser.add_argument("--out", default="data/raw")
    parser.add_argument("--max-records", type=int, default=None, help="Optional limit for datastore sources")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for key, meta in manifest.get("data_gov", {}).items():
        dataset_id = meta["dataset_id"]
        api_type = meta.get("api_type", "")
        print(f"Downloading {key} ({api_type})...")
        if api_type == "datastore_search":
            out_path = out_dir / f"{key}.csv"
            count = download_datastore(dataset_id, out_path, max_records=args.max_records)
            summary.append({"key": key, "path": str(out_path), "records": count})
        elif api_type == "poll_download_geojson":
            out_path = out_dir / f"{key}.geojson"
            download_poll_file(dataset_id, out_path)
            summary.append({"key": key, "path": str(out_path), "records": None})
        else:
            print(f"Skipping unsupported api_type={api_type} for {key}")

    summary_path = out_dir / "download_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
