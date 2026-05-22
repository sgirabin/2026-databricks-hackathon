from __future__ import annotations

import os
from typing import Any

import pandas as pd

from .models import PickCard


def _can_use_sql() -> bool:
    return os.getenv("USE_DATABRICKS_SQL", "false").lower() == "true" and bool(
        os.getenv("DATABRICKS_SERVER_HOSTNAME") and os.getenv("DATABRICKS_HTTP_PATH") and os.getenv("DATABRICKS_TOKEN")
    )


def load_gold_candidate_cards(limit: int = 300) -> list[PickCard]:
    """Load GoAround candidate cards from Databricks SQL / Delta tables.

    Expected table from databricks/setup_open_data_delta.py:
      <catalog>.<schema>.gold_candidate_cards

    Required environment variables:
      USE_DATABRICKS_SQL=true
      DATABRICKS_SERVER_HOSTNAME=<workspace-host-without-https>
      DATABRICKS_HTTP_PATH=<serverless-sql-warehouse-http-path>
      DATABRICKS_TOKEN=<PAT or app secret>
      GOAROUND_CATALOG=main
      GOAROUND_SCHEMA=goaround_sg

    The app falls back to public APIs if these variables are not configured.
    """

    if not _can_use_sql():
        return []

    try:
        from databricks import sql
    except Exception:
        return []

    catalog = os.getenv("GOAROUND_CATALOG", "main")
    schema = os.getenv("GOAROUND_SCHEMA", "goaround_sg")
    table = f"{catalog}.{schema}.gold_candidate_cards"

    query = f"""
        SELECT
          card_type,
          category,
          title,
          description,
          source_name,
          source_url,
          lat,
          lon,
          freshness_score,
          source_reliability
        FROM {table}
        WHERE source_url IS NOT NULL
        LIMIT {int(limit)}
    """

    try:
        with sql.connect(
            server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
            http_path=os.environ["DATABRICKS_HTTP_PATH"],
            access_token=os.environ["DATABRICKS_TOKEN"],
        ) as conn:
            df = pd.read_sql(query, conn)
    except Exception:
        return []

    cards: list[PickCard] = []
    for idx, row in df.iterrows():
        category = str(row.get("category") or "local_update")
        card_type = str(row.get("card_type") or "local_update")
        title = str(row.get("title") or category)
        cards.append(
            PickCard(
                id=f"lakehouse-{idx}-{abs(hash(title)) % 100000}",
                card_type=card_type,
                category=category,
                title=title,
                description=str(row.get("description") or f"Source-backed {category} candidate from Databricks Lakehouse."),
                source_name=str(row.get("source_name") or "Databricks Lakehouse"),
                source_url=str(row.get("source_url") or "https://data.gov.sg/"),
                lat=None if pd.isna(row.get("lat")) else float(row.get("lat")),
                lon=None if pd.isna(row.get("lon")) else float(row.get("lon")),
                location_name=title,
                tags=(category, card_type, "lakehouse", "open data"),
                freshness_score=float(row.get("freshness_score") or 0.55),
                source_reliability=float(row.get("source_reliability") or 0.82),
                metadata={"source_table": table},
            )
        )
    return cards
