from __future__ import annotations

import json
import os
from datetime import datetime
from uuid import uuid4

from .models import PickCard

BUSINESS_PROMOTIONS_COLUMNS = """
    id STRING,
    card_type STRING,
    category STRING,
    title STRING,
    description STRING,
    source_name STRING,
    source_url STRING,
    lat DOUBLE,
    lon DOUBLE,
    location_name STRING,
    valid_until STRING,
    tags STRING,
    source_reliability DOUBLE,
    freshness_score DOUBLE,
    submitted_at STRING
"""


def create_business_promo_card(
    *,
    business_name: str,
    title: str,
    description: str,
    category: str,
    source_url: str,
    lat: float,
    lon: float,
    location_name: str,
    valid_until: str | None,
    tags: list[str] | tuple[str, ...],
) -> PickCard:
    """Create a source-backed business promotion card."""
    safe_tags = tuple(sorted({t.strip().lower() for t in tags if t and t.strip()}))
    return PickCard(
        id=f"business-{uuid4().hex[:10]}",
        card_type="deal",
        category=category or "business promo",
        title=title,
        description=description,
        source_name=business_name,
        source_url=source_url,
        lat=lat,
        lon=lon,
        location_name=location_name,
        end_at=valid_until,
        tags=safe_tags + ("business", "deal", "promotion"),
        source_reliability=0.68,
        freshness_score=0.9,
        business_submitted=True,
        metadata={"submitted_at": datetime.now().isoformat(timespec="seconds")},
    )


def load_local_promotions() -> list[PickCard]:
    """Helper to load promotions from local JSON file fallback."""
    path = "data/business_promotions.json"
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cards = []
        for item in data:
            cards.append(
                PickCard(
                    id=item.get("id"),
                    card_type=item.get("card_type", "deal"),
                    title=item.get("title"),
                    description=item.get("description"),
                    source_name=item.get("source_name") or "Business Promotion",
                    source_url=item.get("source_url") or "https://data.gov.sg/",
                    category=item.get("category") or "deal",
                    lat=None if item.get("lat") is None else float(item["lat"]),
                    lon=None if item.get("lon") is None else float(item["lon"]),
                    location_name=item.get("location_name") or item.get("title"),
                    end_at=item.get("end_at"),
                    tags=tuple(item.get("tags", [])),
                    source_reliability=float(item.get("source_reliability", 0.68)),
                    freshness_score=float(item.get("freshness_score", 0.9)),
                    business_submitted=True,
                    metadata=item.get("metadata", {}),
                )
            )
        return cards
    except Exception as exc:
        print(f"Failed to load local promotions: {exc}")
        return []


def save_local_promotion(card: PickCard) -> None:
    """Helper to save a promotion to local JSON file fallback."""
    path = "data/business_promotions.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Load existing local promotions
    cards = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cards = json.load(f)
        except Exception:
            cards = []

    # Append new card as dictionary
    card_dict = {
        "id": card.id,
        "card_type": card.card_type,
        "category": card.category,
        "title": card.title,
        "description": card.description,
        "source_name": card.source_name,
        "source_url": card.source_url,
        "lat": card.lat,
        "lon": card.lon,
        "location_name": card.location_name,
        "end_at": card.end_at,
        "tags": list(card.tags),
        "source_reliability": card.source_reliability,
        "freshness_score": card.freshness_score,
        "metadata": card.metadata,
    }
    cards.append(card_dict)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)
    except Exception as exc:
        print(f"Failed to save local promotion: {exc}")


def load_business_promotions(
    user_lat: float,
    user_lon: float,
    settings: tuple[str | None, str | None, str | None, str, str],
) -> list[PickCard]:
    """Load nearby promotions from Databricks Delta table; merges with local fallback."""
    host, http_path, token, catalog, schema = settings
    local_cards = load_local_promotions()

    if not token or not host:
        return local_cards

    table = f"{catalog}.{schema}.business_promotions"
    lat_sql = float(user_lat)
    lon_sql = float(user_lon)
    distance_sql = (
        f"SQRT(POWER((lat - {lat_sql}) * 111320, 2) + "
        f"POWER((lon - {lon_sql}) * 111320 * COS(RADIANS({lat_sql})), 2))"
    )

    query = f"""
        SELECT *, {distance_sql} AS distance_m 
        FROM {table}
        ORDER BY distance_m ASC
        LIMIT 50
    """

    try:
        from databricks import sql
        with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        db_cards = []
        for r in rows:
            tags = [t.strip() for t in r.get("tags", "").split(",") if t.strip()]
            db_cards.append(PickCard(
                id=r.get("id"),
                card_type=r.get("card_type") or "deal",
                title=r.get("title"),
                description=r.get("description"),
                source_name=r.get("source_name") or "Business Promotion",
                source_url=r.get("source_url") or "https://data.gov.sg/",
                category=r.get("category") or "deal",
                lat=None if r.get("lat") is None else float(r["lat"]),
                lon=None if r.get("lon") is None else float(r["lon"]),
                location_name=r.get("location_name") or r.get("title"),
                end_at=r.get("valid_until"),
                tags=tuple(tags),
                source_reliability=float(r.get("source_reliability") or 0.68),
                freshness_score=float(r.get("freshness_score") or 0.9),
                business_submitted=True,
                metadata={"submitted_at": r.get("submitted_at")},
            ))
        
        # Merge both and deduplicate by id
        merged = {c.id: c for c in local_cards}
        for card in db_cards:
            merged[card.id] = card
        return list(merged.values())

    except Exception as exc:
        print(f"Failed to query promotions from Databricks SQL: {exc}")
        return local_cards


def save_business_promotion(
    card: PickCard,
    settings: tuple[str | None, str | None, str | None, str, str],
) -> bool:
    """Save business promotion to Databricks Delta table; fallback to local JSON on error."""
    host, http_path, token, catalog, schema = settings
    
    # Always save locally first as a fallback
    save_local_promotion(card)

    if not token or not host:
        return False

    table = f"{catalog}.{schema}.business_promotions"
    tags_str = ",".join(card.tags)
    submitted_at = card.metadata.get("submitted_at", datetime.now().isoformat())

    def clean(s: str | None) -> str:
        if s is None:
            return ""
        return s.replace("'", "''")

    create_query = f"CREATE TABLE IF NOT EXISTS {table} ({BUSINESS_PROMOTIONS_COLUMNS}) USING delta"
    query = f"""
        INSERT INTO {table} (
            id,
            card_type,
            category,
            title,
            description,
            source_name,
            source_url,
            lat,
            lon,
            location_name,
            valid_until,
            tags,
            source_reliability,
            freshness_score,
            submitted_at
        ) VALUES (
            '{clean(card.id)}',
            '{clean(card.card_type)}',
            '{clean(card.category)}',
            '{clean(card.title)}',
            '{clean(card.description)}',
            '{clean(card.source_name)}',
            '{clean(card.source_url)}',
            {float(card.lat or 0.0)},
            {float(card.lon or 0.0)},
            '{clean(card.location_name)}',
            '{clean(card.end_at)}',
            '{clean(tags_str)}',
            {float(card.source_reliability or 0.68)},
            {float(card.freshness_score or 0.9)},
            '{clean(submitted_at)}'
        )
    """

    try:
        from databricks import sql
        with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
            with conn.cursor() as cursor:
                cursor.execute(create_query)
                cursor.execute(query)
            commit = getattr(conn, "commit", None)
            if commit:
                commit()
        print(f"Successfully ingested promotion '{card.title}' into Databricks SQL table {table}.")
        return True
    except Exception as exc:
        print(f"Failed to ingest promotion to Databricks SQL: {exc}. Saved locally.")
        return False
