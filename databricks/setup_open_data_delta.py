# Databricks notebook source
# MAGIC %md
# MAGIC # GoAround SG - Open Data Lakehouse Setup
# MAGIC
# MAGIC This notebook/script loads key public open-data sources into Delta tables.
# MAGIC
# MAGIC The Databricks App can run directly from public APIs for fast demo deployment,
# MAGIC but this setup shows the intended Lakehouse architecture for production:
# MAGIC
# MAGIC ```text
# MAGIC Public open data / APIs
# MAGIC   -> Bronze raw tables
# MAGIC   -> Silver cleaned local entities
# MAGIC   -> Gold candidate cards / Today’s Picks features
# MAGIC ```
# MAGIC
# MAGIC Recommended serverless execution:
# MAGIC - Run on Databricks Serverless notebook or serverless job compute.
# MAGIC - No classic cluster is required.

# COMMAND ----------

import json
import re
from datetime import datetime
from typing import Any

import pandas as pd
import requests

# COMMAND ----------

CATALOG = dbutils.widgets.get("catalog") if "dbutils" in globals() else "main"
SCHEMA = dbutils.widgets.get("schema") if "dbutils" in globals() else "goaround_sg"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")

# COMMAND ----------

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"

DATASETS = {
    "hawker_centres": "d_4a086da0a5553be1d89383cd",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
}

SOURCE_REGISTRY = [
    {"source_name": "FairPrice Promotions", "category": "grocery", "source_url": "https://www.fairprice.com.sg/promotions", "tags": "grocery,deal,resident,budget,weekly"},
    {"source_name": "Sheng Siong Promotions", "category": "grocery", "source_url": "https://shengsiong.com.sg/promotions", "tags": "grocery,deal,resident,budget,weekly"},
    {"source_name": "Cold Storage Promotions", "category": "grocery", "source_url": "https://coldstorage.com.sg/promotions", "tags": "grocery,deal,shopping"},
    {"source_name": "CapitaLand Mall Promotions", "category": "mall", "source_url": "https://www.capitaland.com/sg/malls/promotions.html", "tags": "mall,deal,shopping,family,weekend,tourist"},
    {"source_name": "Frasers Property Mall Promotions", "category": "mall", "source_url": "https://www.frasersproperty.com/sg/malls/promotions", "tags": "mall,deal,shopping,family,weekend"},
    {"source_name": "OnePA Events", "category": "community", "source_url": "https://www.onepa.gov.sg/events", "tags": "community,event,family,weekend,resident"},
    {"source_name": "NLB Events", "category": "family_learning", "source_url": "https://www.nlb.gov.sg/main/whats-on/events", "tags": "event,family,learning,indoor,rainy day,weekend"},
    {"source_name": "ActiveSG Circle", "category": "fitness", "source_url": "https://www.activesgcircle.gov.sg/", "tags": "fitness,event,sports,weekend,family"},
    {"source_name": "URA Draft Master Plan", "category": "future_plans", "source_url": "https://www.uradraftmasterplan.gov.sg/", "tags": "future plans,local update,resident,buyer mode"},
    {"source_name": "LTA Upcoming Projects", "category": "transport", "source_url": "https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html", "tags": "transport,local update,future plans,resident,buyer mode"},
]

# COMMAND ----------

def clean_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def write_delta(df: pd.DataFrame, table_name: str) -> None:
    if df.empty:
        print(f"Skipping empty table: {table_name}")
        return
    sdf = spark.createDataFrame(df)
    sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{CATALOG}.{SCHEMA}.{table_name}")
    print(f"Wrote {len(df):,} rows to {CATALOG}.{SCHEMA}.{table_name}")


def poll_download_url(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    gj = requests.get(poll_download_url(dataset_id), timeout=90).json()
    rows = []
    for feature in gj.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        props = feature.get("properties") or {}
        if geom.get("type") != "Point" or len(coords) < 2:
            continue
        name = props.get("NAME") or props.get("Name") or props.get("ADDRESSBUILDINGNAME") or props.get("DESCRIPTION") or category
        address = " ".join([
            str(props.get("ADDRESSBLOCKHOUSENUMBER") or ""),
            str(props.get("ADDRESSSTREETNAME") or ""),
        ]).strip() or str(props.get("ADDRESS") or "")
        rows.append({
            "source_dataset": dataset_id,
            "category": category,
            "name": str(name),
            "address": address,
            "postal_code": str(props.get("ADDRESSPOSTALCODE") or ""),
            "latitude": float(coords[1]),
            "longitude": float(coords[0]),
            "source": "data.gov.sg",
            "loaded_at": datetime.utcnow().isoformat(timespec="seconds"),
        })
    return pd.DataFrame(rows)

# COMMAND ----------

# Bronze: raw-ish source points normalised enough for Delta storage.
bronze_frames = []
for category, dataset_id in DATASETS.items():
    df = load_geojson_points(dataset_id, category)
    write_delta(df, f"bronze_{category}")
    bronze_frames.append(df)

# COMMAND ----------

# Silver: unified local entities.
silver_entities = pd.concat(bronze_frames, ignore_index=True) if bronze_frames else pd.DataFrame()
silver_entities = silver_entities.drop_duplicates(["category", "name", "latitude", "longitude"])
write_delta(silver_entities, "silver_local_entities")

# COMMAND ----------

# Silver: source registry for deals/events/local updates.
source_registry = pd.DataFrame(SOURCE_REGISTRY)
source_registry["loaded_at"] = datetime.utcnow().isoformat(timespec="seconds")
write_delta(source_registry, "silver_source_registry")

# COMMAND ----------

# Gold: candidate Today’s Picks from open-data entities.
if not silver_entities.empty:
    gold_cards = silver_entities.rename(columns={"latitude": "lat", "longitude": "lon"}).copy()
    gold_cards["card_type"] = gold_cards["category"].map({"hawker_centres": "food", "supermarkets": "deal", "community_clubs": "event"}).fillna("local_update")
    gold_cards["title"] = gold_cards["name"]
    gold_cards["description"] = gold_cards.apply(lambda r: f"Nearby {r['category'].replace('_', ' ')} from data.gov.sg open data.", axis=1)
    gold_cards["source_name"] = "data.gov.sg open data"
    gold_cards["source_url"] = "https://data.gov.sg/"
    gold_cards["freshness_score"] = 0.55
    gold_cards["source_reliability"] = 0.82
    gold_cards = gold_cards[["card_type", "category", "title", "description", "source_name", "source_url", "lat", "lon", "freshness_score", "source_reliability", "loaded_at"]]
    write_delta(gold_cards, "gold_candidate_cards")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tables created
# MAGIC
# MAGIC - `bronze_hawker_centres`
# MAGIC - `bronze_supermarkets`
# MAGIC - `bronze_community_clubs`
# MAGIC - `silver_local_entities`
# MAGIC - `silver_source_registry`
# MAGIC - `gold_candidate_cards`
# MAGIC
# MAGIC These tables can be used by Genie, dashboards, Model Serving prompts, and the GoAround SG app in a production setup.
