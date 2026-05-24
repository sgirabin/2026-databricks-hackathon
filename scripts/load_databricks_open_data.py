from __future__ import annotations

import os
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from databricks import sql


POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"

DATASETS = {
    "hawker_centres": "d_4a086da0a5553be1d89383cd90d07ecd",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
}

LOCAL_GEOJSON_DATASETS = {
    "community_clubs": ("data/CommunityClubs.geojson", "event", "community", "OnePA / People's Association", "https://www.onepa.gov.sg/"),
    "bus_stops": ("data/LTABusStop.geojson", "transport", "transport", "LTA static bus stops", "https://datamall.lta.gov.sg/"),
    "mrt_station_exits": ("data/LTAMRTStationExitGEOJSON.geojson", "transport", "transport", "LTA MRT station exits", "https://www.lta.gov.sg/"),
    "chas_clinics": ("data/CHASClinics.geojson", "local_update", "health", "MOH CHAS clinics", "https://www.chas.sg/"),
    "healthier_eateries": ("data/HealthierEateries.geojson", "food", "food", "HPB healthier eateries", "https://www.hpb.gov.sg/"),
    "childcare_services": ("data/ChildCareServices.geojson", "local_update", "family", "ECDA childcare services", "https://www.ecda.gov.sg/"),
    "preschools": ("data/PreSchoolsLocation.geojson", "local_update", "family", "ECDA preschools", "https://www.ecda.gov.sg/"),
    "kindergartens": ("data/Kindergartens.geojson", "local_update", "family", "MOE kindergartens", "https://www.moe.gov.sg/"),
    "parks": ("data/Parks.geojson", "event", "park", "NParks parks", "https://www.nparks.gov.sg/"),
    "parks_sg": ("data/ParksSG.geojson", "event", "park", "NParks parks", "https://www.nparks.gov.sg/"),
    "tourist_attractions": ("data/TouristAttractions.geojson", "plan", "tourist", "Singapore Tourism Board", "https://www.visitsingapore.com/"),
    "gyms": ("data/GymsSGGEOJSON.geojson", "event", "fitness", "SportSG gyms", "https://www.myactivesg.com/"),
    "sports_facilities": ("data/SportSGSportFacilitiesGEOJSON.geojson", "event", "fitness", "SportSG sport facilities", "https://www.myactivesg.com/"),
    "eldercare_services": ("data/EldercareServices.geojson", "local_update", "health", "Eldercare services", "https://www.aic.sg/"),
    "bicycle_racks": ("data/LTABicycleRackGEOJSON.geojson", "transport", "transport", "LTA bicycle racks", "https://www.lta.gov.sg/"),
    "ewaste_recycling": ("data/EwasteRecyclingGEOJSON.geojson", "local_update", "recycling", "NEA e-waste recycling", "https://www.nea.gov.sg/"),
}

LOCAL_CSV_DATASETS = {
    "supermarkets": ("data/ListofSupermarketLicences.csv", "deal", "grocery", "SFA supermarket licences", "https://www.sfa.gov.sg/"),
    "hawker_closures": ("data/DatesofHawkerCentresClosure.csv", "local_update", "food", "NEA hawker centre closures", "https://www.nea.gov.sg/"),
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


def api_headers() -> dict[str, str]:
    headers = {"User-Agent": "goaround-sg-databricks-loader/0.1"}
    if os.getenv("DATA_GOV_API_KEY"):
        headers["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return headers


def poll_download_url(dataset_id: str) -> str:
    for attempt in range(3):
        response = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=api_headers(), timeout=45)
        if response.status_code != 429:
            response.raise_for_status()
            return response.json()["data"]["url"]
        time.sleep(2 + attempt * 3)
    response.raise_for_status()
    raise RuntimeError("unreachable")


def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    response = requests.get(poll_download_url(dataset_id), headers=api_headers(), timeout=90)
    response.raise_for_status()
    geojson = response.json()
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        props = feature.get("properties") or {}
        if geom.get("type") != "Point" or len(coords) < 2:
            continue
        name = (
            props.get("NAME")
            or props.get("Name")
            or props.get("ADDRESSBUILDINGNAME")
            or props.get("DESCRIPTION")
            or category
        )
        address = " ".join(
            [
                str(props.get("ADDRESSBLOCKHOUSENUMBER") or ""),
                str(props.get("ADDRESSSTREETNAME") or ""),
            ]
        ).strip() or str(props.get("ADDRESS") or "")
        rows.append(
            {
                "source_dataset": dataset_id,
                "category": category,
                "name": str(name),
                "address": address,
                "postal_code": str(props.get("ADDRESSPOSTALCODE") or ""),
                "latitude": float(coords[1]),
                "longitude": float(coords[0]),
                "source": "data.gov.sg",
                "loaded_at": loaded_at,
            }
        )
    return pd.DataFrame(rows)


def extract_description_fields(description: str | None) -> dict[str, str]:
    if not description:
        return {}
    pairs = re.findall(r"<th[^>]*>\s*([^<]+?)\s*</th>\s*<td[^>]*>\s*(.*?)\s*</td>", description, re.I | re.S)
    fields: dict[str, str] = {}
    for key, value in pairs:
        clean_key = re.sub(r"\s+", " ", key).strip().upper()
        clean_value = re.sub(r"<[^>]+>", " ", value)
        clean_value = re.sub(r"\s+", " ", clean_value).strip()
        fields[clean_key] = clean_value
    return fields


def local_geojson_entities() -> pd.DataFrame:
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for dataset_name, (path, card_type, category, source_name, source_url) in LOCAL_GEOJSON_DATASETS.items():
        file_path = Path(path)
        if not file_path.exists():
            continue
        data = json.loads(file_path.read_text(encoding="utf-8"))
        for idx, feature in enumerate(data.get("features", [])):
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if geom.get("type") != "Point" or len(coords) < 2:
                continue
            props = feature.get("properties") or {}
            fields = extract_description_fields(props.get("Description"))
            name = (
                props.get("NAME")
                or props.get("Name")
                or props.get("STATION_NA")
                or props.get("PAGETITLE")
                or props.get("HCI_NAME")
                or fields.get("NAME")
                or fields.get("CENTRE_NAME")
                or fields.get("HCI_NAME")
                or fields.get("DESCRIPTION")
                or dataset_name.replace("_", " ").title()
            )
            address = (
                props.get("ADDRESS")
                or " ".join(
                    str(x or "")
                    for x in [
                        props.get("ADDRESSBLOCKHOUSENUMBER") or fields.get("ADDRESSBLOCKHOUSENUMBER"),
                        props.get("ADDRESSSTREETNAME") or fields.get("ADDRESSSTREETNAME"),
                        props.get("ADDRESSBUILDINGNAME") or fields.get("ADDRESSBUILDINGNAME"),
                    ]
                ).strip()
                or props.get("STREET_NAME")
                or fields.get("STREET_NAME")
                or ""
            )
            postal_code = str(
                props.get("ADDRESSPOSTALCODE")
                or props.get("POSTALCODE")
                or props.get("POSTAL_CD")
                or fields.get("ADDRESSPOSTALCODE")
                or fields.get("POSTAL_CD")
                or ""
            )
            description = (
                props.get("OVERVIEW")
                or props.get("DESCRIPTION")
                or fields.get("DESCRIPTION")
                or f"{category.replace('_', ' ').title()} location from local open-data file."
            )
            rows.append(
                {
                    "source_dataset": dataset_name,
                    "card_type": card_type,
                    "category": category,
                    "name": str(name),
                    "description": str(description)[:900],
                    "address": str(address),
                    "postal_code": postal_code,
                    "lat": float(coords[1]),
                    "lon": float(coords[0]),
                    "source_name": source_name,
                    "source_url": source_url,
                    "loaded_at": loaded_at,
                }
            )
    return pd.DataFrame(rows)


def geocode_postal(postal_code: str) -> tuple[float | None, float | None]:
    if not postal_code or str(postal_code).lower() == "nan":
        return None, None
    try:
        response = requests.get(
            "https://www.onemap.gov.sg/api/common/elastic/search",
            params={"searchVal": str(postal_code), "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            return None, None
        return float(results[0]["LATITUDE"]), float(results[0]["LONGITUDE"])
    except Exception:
        return None, None


def local_csv_entities() -> pd.DataFrame:
    loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    supermarket_path = Path(LOCAL_CSV_DATASETS["supermarkets"][0])
    if supermarket_path.exists():
        supermarkets = pd.read_csv(supermarket_path).drop_duplicates(["licensee_name", "postal_code"])
        geocode_cache: dict[str, tuple[float | None, float | None]] = {}
        for row in supermarkets.to_dict("records"):
            postal = str(row.get("postal_code") or "")
            if postal not in geocode_cache:
                geocode_cache[postal] = geocode_postal(postal)
                time.sleep(0.05)
            lat, lon = geocode_cache[postal]
            if lat is None or lon is None:
                continue
            business = str(row.get("licensee_name") or "Supermarket").title()
            building = str(row.get("building_name") or "").title()
            street = str(row.get("street_name") or "").title()
            title = business if building.lower() in {"", "na", "nan"} else f"{business} - {building}"
            rows.append(
                {
                    "source_dataset": "supermarkets",
                    "card_type": "deal",
                    "category": "grocery",
                    "name": title,
                    "description": f"Supermarket licence record near {street}. Verify current promotions and opening hours at source.",
                    "address": " ".join(str(x or "") for x in [row.get("block_house_num"), street, postal]).strip(),
                    "postal_code": postal,
                    "lat": lat,
                    "lon": lon,
                    "source_name": "SFA supermarket licences",
                    "source_url": "https://www.sfa.gov.sg/",
                    "loaded_at": loaded_at,
                }
            )

    closure_path = Path(LOCAL_CSV_DATASETS["hawker_closures"][0])
    if closure_path.exists():
        closures = pd.read_csv(closure_path)
        for row in closures.to_dict("records"):
            try:
                lat = float(row.get("latitude_hc"))
                lon = float(row.get("longitude_hc"))
            except (TypeError, ValueError):
                continue
            rows.append(
                {
                    "source_dataset": "hawker_closures",
                    "card_type": "local_update",
                    "category": "food",
                    "name": str(row.get("name") or "Hawker centre closure schedule"),
                    "description": f"2026 cleaning schedule available for this hawker centre. Q2: {row.get('q2_cleaningstartdate')} to {row.get('q2_cleaningenddate')}. Verify before going.",
                    "address": str(row.get("address_myenv") or ""),
                    "postal_code": "",
                    "lat": lat,
                    "lon": lon,
                    "source_name": "NEA hawker centre closure schedule",
                    "source_url": "https://www.nea.gov.sg/",
                    "loaded_at": loaded_at,
                }
            )
    return pd.DataFrame(rows)


def sql_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert_rows(cursor: Any, table: str, columns: list[str], rows: list[dict[str, Any]], batch_size: int = 150) -> None:
    if not rows:
        return
    col_sql = ", ".join(columns)
    for idx in range(0, len(rows), batch_size):
        batch = rows[idx : idx + batch_size]
        values_sql = []
        for row in batch:
            values_sql.append("(" + ", ".join(sql_value(row.get(col)) for col in columns) + ")")
        cursor.execute(f"INSERT INTO {table} ({col_sql}) VALUES " + ", ".join(values_sql))
        print(f"Inserted {min(idx + batch_size, len(rows)):,}/{len(rows):,} rows into {table}", flush=True)


def replace_table(cursor: Any, table: str, schema_sql: str, df: pd.DataFrame) -> None:
    print(f"Replacing {table} with {len(df):,} rows", flush=True)
    cursor.execute(f"CREATE OR REPLACE TABLE {table} ({schema_sql}) USING DELTA")
    insert_rows(cursor, table, list(df.columns), df.to_dict("records"))
    print(f"Wrote {len(df):,} rows to {table}", flush=True)


def main() -> None:
    host = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    http_path = os.environ["DATABRICKS_HTTP_PATH"]
    token = os.environ["DATABRICKS_TOKEN"]
    catalog = os.getenv("GOAROUND_CATALOG", "workspace")
    schema = os.getenv("GOAROUND_SCHEMA", "goaround_sg")
    namespace = f"{catalog}.{schema}"

    bronze_frames: list[pd.DataFrame] = []
    for category, dataset_id in DATASETS.items():
        try:
            df = load_geojson_points(dataset_id, category)
        except requests.HTTPError as exc:
            print(f"Skipping {category}: {exc}")
            df = pd.DataFrame(
                columns=[
                    "source_dataset",
                    "category",
                    "name",
                    "address",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "source",
                    "loaded_at",
                ]
            )
        bronze_frames.append(df)

    silver_entities = (
        pd.concat(bronze_frames, ignore_index=True)
        .drop_duplicates(["category", "name", "latitude", "longitude"])
        .reset_index(drop=True)
    )

    source_registry = pd.DataFrame(SOURCE_REGISTRY)
    source_registry["loaded_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    local_entities = pd.concat([local_geojson_entities(), local_csv_entities()], ignore_index=True)

    gold_cards = silver_entities.rename(columns={"latitude": "lat", "longitude": "lon"}).copy()
    gold_cards["card_type"] = gold_cards["category"].map(
        {"hawker_centres": "food", "supermarkets": "deal", "community_clubs": "event"}
    ).fillna("local_update")
    gold_cards["title"] = gold_cards["name"]
    gold_cards["description"] = gold_cards.apply(
        lambda row: f"Nearby {row['category'].replace('_', ' ')} from data.gov.sg open data.",
        axis=1,
    )
    gold_cards["source_name"] = "data.gov.sg open data"
    gold_cards["source_url"] = "https://data.gov.sg/"
    gold_cards["freshness_score"] = 0.55
    gold_cards["source_reliability"] = 0.82
    gold_cards = gold_cards[
        [
            "card_type",
            "category",
            "title",
            "description",
            "source_name",
            "source_url",
            "lat",
            "lon",
            "freshness_score",
            "source_reliability",
            "loaded_at",
        ]
    ]
    if not local_entities.empty:
        local_gold_cards = local_entities.rename(columns={"name": "title"}).copy()
        local_gold_cards["freshness_score"] = 0.65
        local_gold_cards["source_reliability"] = 0.82
        local_gold_cards = local_gold_cards[
            [
                "card_type",
                "category",
                "title",
                "description",
                "source_name",
                "source_url",
                "lat",
                "lon",
                "freshness_score",
                "source_reliability",
                "loaded_at",
            ]
        ]
        gold_cards = pd.concat([gold_cards, local_gold_cards], ignore_index=True).drop_duplicates(
            ["card_type", "category", "title", "lat", "lon"]
        )

    with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
        cursor = conn.cursor()
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {namespace}")
        for category, df in zip(DATASETS, bronze_frames, strict=True):
            replace_table(
                cursor,
                f"{namespace}.bronze_{category}",
                "source_dataset STRING, category STRING, name STRING, address STRING, postal_code STRING, latitude DOUBLE, longitude DOUBLE, source STRING, loaded_at STRING",
                df,
            )
        replace_table(
            cursor,
            f"{namespace}.silver_local_entities",
            "source_dataset STRING, category STRING, name STRING, address STRING, postal_code STRING, latitude DOUBLE, longitude DOUBLE, source STRING, loaded_at STRING",
            silver_entities,
        )
        replace_table(
            cursor,
            f"{namespace}.silver_source_registry",
            "source_name STRING, category STRING, source_url STRING, tags STRING, loaded_at STRING",
            source_registry,
        )
        if not local_entities.empty:
            replace_table(
                cursor,
                f"{namespace}.silver_local_static_entities",
                "source_dataset STRING, card_type STRING, category STRING, name STRING, description STRING, address STRING, postal_code STRING, lat DOUBLE, lon DOUBLE, source_name STRING, source_url STRING, loaded_at STRING",
                local_entities,
            )
        replace_table(
            cursor,
            f"{namespace}.gold_candidate_cards",
            "card_type STRING, category STRING, title STRING, description STRING, source_name STRING, source_url STRING, lat DOUBLE, lon DOUBLE, freshness_score DOUBLE, source_reliability DOUBLE, loaded_at STRING",
            gold_cards,
        )
        cursor.execute(f"SELECT COUNT(*) FROM {namespace}.gold_candidate_cards")
        print(f"Verified gold_candidate_cards rows: {cursor.fetchall()[0][0]:,}")
        cursor.close()


if __name__ == "__main__":
    main()
