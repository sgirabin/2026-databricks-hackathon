from __future__ import annotations

import math
import os
import re
import time
import urllib.parse
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="GoAround SG", page_icon="📍", layout="wide")

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
DATA_GOV_WEATHER_2H = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
DATA_GOV_RAINFALL = "https://api.data.gov.sg/v1/environment/rainfall"
LTA_BUS_STOPS_URL = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"

DATASETS = {
    "hdb_resale": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",
    "hawker_centres": "d_4a086da0a5553be1d89383cd90d07ecd",
    "schools": "d_688b934f82c1059ed0a6993d2a829089",
    "preschools": "d_696c994c50745b079b3684f0e90ffc53",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
    "dengue_clusters": "d_dbfabf16158d1b0e1c420627c0819168",
}

CREDIBLE_DOMAINS = [
    "channelnewsasia.com", "straitstimes.com", "businesstimes.com.sg", "todayonline.com",
    "mothership.sg", "scdf.gov.sg", "police.gov.sg", "gov.sg", "hdb.gov.sg", "ura.gov.sg", "lta.gov.sg",
]

PROMOTION_SOURCES = [
    ("FairPrice promotions", "https://www.fairprice.com.sg/promotions"),
    ("Sheng Siong promotions", "https://shengsiong.com.sg/promotions"),
    ("Cold Storage promotions", "https://coldstorage.com.sg/promotions"),
    ("CapitaLand mall deals", "https://www.capitaland.com/sg/malls/promotions.html"),
    ("Frasers Property retail promotions", "https://www.frasersproperty.com/sg/malls/promotions"),
    ("Lendlease Plus deals", "https://www.lendleaseplus.com/sg/en/promotions.html"),
]

EVENT_SOURCES = [
    ("OnePA events", "https://www.onepa.gov.sg/events"),
    ("NLB events", "https://www.nlb.gov.sg/main/whats-on/events"),
    ("ActiveSG programmes", "https://www.activesgcircle.gov.sg/"),
    ("People's Association", "https://www.pa.gov.sg/"),
    ("HDB press releases", "https://www.hdb.gov.sg/about-us/news-and-publications/press-releases"),
    ("LTA upcoming projects", "https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html"),
    ("URA Draft Master Plan", "https://www.uradraftmasterplan.gov.sg/"),
]

PERSONA_WEIGHTS = {
    "Balanced resident": {"transport": 0.25, "daily": 0.30, "family": 0.15, "environment": 0.15, "evidence": 0.15},
    "Family with young child": {"transport": 0.18, "daily": 0.22, "family": 0.35, "environment": 0.10, "evidence": 0.15},
    "Car-free commuter": {"transport": 0.45, "daily": 0.25, "family": 0.05, "environment": 0.10, "evidence": 0.15},
    "Elderly parents nearby": {"transport": 0.22, "daily": 0.35, "family": 0.08, "environment": 0.15, "evidence": 0.20},
    "Buyer / tenant evaluating area": {"transport": 0.25, "daily": 0.20, "family": 0.15, "environment": 0.10, "evidence": 0.10},
}

# ----------------------------- Utilities -----------------------------

def api_headers() -> dict[str, str]:
    headers = {"User-Agent": "goaround-sg-hackathon/0.3"}
    if os.getenv("DATA_GOV_API_KEY"):
        headers["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return headers


def lta_headers() -> dict[str, str]:
    key = os.getenv("LTA_ACCOUNT_KEY", "")
    return {"AccountKey": key, "accept": "application/json"}


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in out.columns]
    return out.drop(columns=["_id"], errors="ignore")


def first_value(props: dict[str, Any], candidates: list[str], default: str = "") -> str:
    lower = {str(k).lower(): v for k, v in props.items()}
    for c in candidates:
        if c.lower() in lower and pd.notna(lower[c.lower()]) and str(lower[c.lower()]).strip():
            return str(lower[c.lower()]).strip()
    return default


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_score(d: float | None, excellent: int, good: int, maxd: int) -> float:
    if d is None:
        return 35.0
    if d <= excellent:
        return 100.0
    if d <= good:
        return 80.0
    if d <= maxd:
        return max(25.0, 80 - (d - good) / (maxd - good) * 55)
    return 10.0


def dist(v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    v = float(v)
    return f"{v:,.0f} m" if v < 1000 else f"{v/1000:.1f} km"


def money(v: Any) -> str:
    return "n/a" if v is None or pd.isna(v) else f"S${float(v):,.0f}"


def google_search_link(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)


# ----------------------------- Data loaders -----------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def datastore_search(dataset_id: str, limit: int = 5000, max_records: int | None = None) -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        page_limit = limit if max_records is None else min(limit, max_records - len(rows))
        if page_limit <= 0:
            break
        r = requests.get(DATASTORE_URL, params={"resource_id": dataset_id, "limit": page_limit, "offset": offset}, headers=api_headers(), timeout=45)
        r.raise_for_status()
        result = r.json().get("result", {})
        page = result.get("records", [])
        rows.extend(page)
        offset += len(page)
        if not page or offset >= int(result.get("total", offset)):
            break
    return clean_columns(pd.DataFrame(rows))


@st.cache_data(ttl=86400, show_spinner=False)
def poll_download(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=api_headers(), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


@st.cache_data(ttl=86400, show_spinner=False)
def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    try:
        gj = requests.get(poll_download(dataset_id), headers=api_headers(), timeout=90).json()
        rows = []
        for feature in gj.get("features", []):
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if geom.get("type") == "Point" and len(coords) >= 2:
                props = feature.get("properties") or {}
                name = first_value(props, ["name", "NAME", "ADDRESSBUILDINGNAME", "DESCRIPTION"], category)
                block = first_value(props, ["ADDRESSBLOCKHOUSENUMBER", "block"], "")
                street = first_value(props, ["ADDRESSSTREETNAME", "street", "address"], "")
                postal = first_value(props, ["ADDRESSPOSTALCODE", "postal_code", "postal"], "")
                address = " ".join([block, street]).strip() or first_value(props, ["ADDRESS", "description"], "")
                rows.append({"category": category, "name": name, "address": address, "postal_code": postal, "lat": float(coords[1]), "lon": float(coords[0]), "source": "data.gov.sg"})
        return pd.DataFrame(rows)
    except Exception as exc:
        st.toast(f"Could not load {category}: {exc}", icon="⚠️")
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=30)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {"address": best.get("ADDRESS") or query, "building": best.get("BUILDING") or "", "road_name": best.get("ROAD_NAME") or "", "postal_code": best.get("POSTAL") or "", "lat": float(best["LATITUDE"]), "lon": float(best["LONGITUDE"])}


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_many(rows: list[dict[str, str]], category: str, max_rows: int) -> pd.DataFrame:
    out = []
    for i, item in enumerate(rows[:max_rows]):
        query = item.get("query") or item.get("postal_code") or item.get("address") or item.get("name", "")
        if not query:
            continue
        try:
            g = geocode(query)
            out.append({"category": category, "name": item.get("name") or g.get("building") or query, "address": item.get("address") or g["address"], "postal_code": item.get("postal_code") or g.get("postal_code", ""), "lat": g["lat"], "lon": g["lon"], "source": item.get("source", "data.gov.sg + OneMap geocode")})
        except Exception:
            pass
        if i % 20 == 19:
            time.sleep(0.2)
    return pd.DataFrame(out)


@st.cache_data(ttl=86400, show_spinner=False)
def load_schools(max_geocode_rows: int = 400) -> pd.DataFrame:
    df = datastore_search(DATASETS["schools"], max_records=800)
    if df.empty:
        return pd.DataFrame()
    name_col = next((c for c in ["school_name", "name"] if c in df.columns), None)
    address_col = next((c for c in ["address", "school_address"] if c in df.columns), None)
    postal_col = next((c for c in ["postal_code", "postal"] if c in df.columns), None)
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "lng"] if c in df.columns), None)
    if lat_col and lon_col and name_col:
        return pd.DataFrame({"category": "school", "name": df[name_col], "address": df[address_col] if address_col else "", "postal_code": df[postal_col] if postal_col else "", "lat": pd.to_numeric(df[lat_col], errors="coerce"), "lon": pd.to_numeric(df[lon_col], errors="coerce"), "source": "data.gov.sg"}).dropna(subset=["lat", "lon"])
    items = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        address = str(row.get(address_col, "")).strip() if address_col else ""
        postal = str(row.get(postal_col, "")).strip() if postal_col else ""
        if name:
            items.append({"name": name, "address": address, "postal_code": postal, "query": postal or address or name})
    return geocode_many(items, "school", max_geocode_rows)


@st.cache_data(ttl=86400, show_spinner=False)
def load_preschools(max_geocode_rows: int = 700) -> pd.DataFrame:
    df = datastore_search(DATASETS["preschools"], max_records=2000)
    if df.empty:
        return pd.DataFrame()
    name_col = next((c for c in ["centre_name", "center_name", "name"] if c in df.columns), None)
    address_col = next((c for c in ["centre_address", "address"] if c in df.columns), None)
    postal_col = next((c for c in ["postal_code", "postal"] if c in df.columns), None)
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "lng"] if c in df.columns), None)
    if lat_col and lon_col and name_col:
        return pd.DataFrame({"category": "preschool", "name": df[name_col], "address": df[address_col] if address_col else "", "postal_code": df[postal_col] if postal_col else "", "lat": pd.to_numeric(df[lat_col], errors="coerce"), "lon": pd.to_numeric(df[lon_col], errors="coerce"), "source": "data.gov.sg"}).dropna(subset=["lat", "lon"])
    items = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        address = str(row.get(address_col, "")).strip() if address_col else ""
        postal = str(row.get(postal_col, "")).strip() if postal_col else ""
        if name:
            items.append({"name": name, "address": address, "postal_code": postal, "query": postal or address or name})
    return geocode_many(items, "preschool", max_geocode_rows)


@st.cache_data(ttl=86400, show_spinner=True)
def load_live_amenities(max_school_geocode: int, max_preschool_geocode: int) -> pd.DataFrame:
    frames = [
        load_geojson_points(DATASETS["hawker_centres"], "hawker_centre"),
        load_geojson_points(DATASETS["supermarkets"], "supermarket"),
        load_geojson_points(DATASETS["community_clubs"], "community_club"),
        load_schools(max_school_geocode),
        load_preschools(max_preschool_geocode),
    ]
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])
    out = pd.concat(frames, ignore_index=True)
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["lat", "lon"]).drop_duplicates(["category", "name", "lat", "lon"])


@st.cache_data(ttl=1800, show_spinner=False)
def load_bus_stops(max_pages: int = 12) -> pd.DataFrame:
    if not os.getenv("LTA_ACCOUNT_KEY"):
        return pd.DataFrame()
    rows = []
    for page in range(max_pages):
        skip = page * 500
        r = requests.get(LTA_BUS_STOPS_URL, params={"$skip": skip}, headers=lta_headers(), timeout=30)
        r.raise_for_status()
        values = r.json().get("value", [])
        rows.extend(values)
        if len(values) < 500:
            break
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(columns={"BusStopCode": "bus_stop_code", "RoadName": "road_name", "Description": "name", "Latitude": "lat", "Longitude": "lon"})
    df["category"] = "bus_stop"
    df["source"] = "LTA DataMall"
    return df[["category", "bus_stop_code", "name", "road_name", "lat", "lon", "source"]].dropna(subset=["lat", "lon"])


@st.cache_data(ttl=30, show_spinner=False)
def get_bus_arrival(bus_stop_code: str) -> pd.DataFrame:
    if not os.getenv("LTA_ACCOUNT_KEY") or not bus_stop_code:
        return pd.DataFrame()
    r = requests.get(LTA_BUS_ARRIVAL_URL, params={"BusStopCode": bus_stop_code}, headers=lta_headers(), timeout=30)
    r.raise_for_status()
    rows = []
    now = datetime.now().astimezone()
    for service in r.json().get("Services", []):
        for key in ["NextBus", "NextBus2", "NextBus3"]:
            bus = service.get(key) or {}
            eta = bus.get("EstimatedArrival")
            if eta:
                try:
                    eta_dt = datetime.fromisoformat(eta.replace("Z", "+00:00")).astimezone()
                    mins = max(0, int((eta_dt - now).total_seconds() // 60))
                except Exception:
                    mins = None
            else:
                mins = None
            rows.append({"service_no": service.get("ServiceNo"), "operator": service.get("Operator"), "arrival_slot": key, "minutes": mins, "load": bus.get("Load"), "type": bus.get("Type")})
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def get_weather_near(lat: float, lon: float) -> dict[str, Any]:
    out = {"forecast_area": None, "forecast": None, "nearest_rain_station": None, "rainfall_mm": None}
    try:
        data = requests.get(DATA_GOV_WEATHER_2H, timeout=20).json()
        meta = data.get("area_metadata", [])
        forecasts = {f["area"]: f.get("forecast") for f in data.get("items", [{}])[0].get("forecasts", [])}
        best = None
        for area in meta:
            loc = area.get("label_location") or {}
            d = haversine_m(lat, lon, float(loc.get("latitude")), float(loc.get("longitude")))
            if best is None or d < best[0]:
                best = (d, area.get("name"))
        if best:
            out["forecast_area"] = best[1]
            out["forecast"] = forecasts.get(best[1])
    except Exception:
        pass
    try:
        data = requests.get(DATA_GOV_RAINFALL, timeout=20).json()
        stations = {s["id"]: s for s in data.get("metadata", {}).get("stations", [])}
        readings = data.get("items", [{}])[0].get("readings", [])
        best = None
        for reading in readings:
            stn = stations.get(reading.get("station_id"))
            if not stn:
                continue
            loc = stn.get("location") or {}
            d = haversine_m(lat, lon, float(loc.get("latitude")), float(loc.get("longitude")))
            if best is None or d < best[0]:
                best = (d, stn.get("name"), reading.get("value"))
        if best:
            out["nearest_rain_station"] = best[1]
            out["rainfall_mm"] = best[2]
    except Exception:
        pass
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def load_dengue_clusters() -> pd.DataFrame:
    try:
        gj = requests.get(poll_download(DATASETS["dengue_clusters"]), headers=api_headers(), timeout=60).json()
        rows = []
        for feature in gj.get("features", []):
            props = feature.get("properties") or {}
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or []
            points = []
            if geom.get("type") == "Polygon" and coords:
                points = coords[0]
            elif geom.get("type") == "MultiPolygon" and coords and coords[0]:
                points = coords[0][0]
            if points:
                lon = sum(p[0] for p in points) / len(points)
                lat = sum(p[1] for p in points) / len(points)
                rows.append({"category": "dengue_cluster", "name": props.get("NAME") or props.get("LOCALITY") or "Dengue cluster", "locality": props.get("LOCALITY", ""), "case_size": props.get("CASE_SIZE"), "lat": lat, "lon": lon, "source": "data.gov.sg / NEA"})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=True)
def load_hdb_resale(max_records: int = 80000) -> pd.DataFrame:
    df = datastore_search(DATASETS["hdb_resale"], max_records=max_records)
    if df.empty:
        return df
    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")
        df["quarter"] = df["month"].dt.to_period("Q").astype(str)
    for c in ["resale_price", "floor_area_sqm"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["town", "flat_type", "street_name", "block", "storey_range"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.upper().str.strip()
    return df


def nearest(df: pd.DataFrame, lat: float, lon: float, radius_m: int, limit: int = 12) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.dropna(subset=["lat", "lon"]).copy()
    out["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in out.itertuples()]
    return out[out.distance_m <= radius_m].sort_values("distance_m").head(limit)


def build_trend(df: pd.DataFrame, town: str, flat_type: str, road_name: str = "") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if df.empty:
        return df, pd.DataFrame(), {}
    out = df.copy()
    if town != "Any":
        out = out[out.town == town]
    if flat_type != "Any":
        out = out[out.flat_type == flat_type]
    tokens = [t for t in re.sub(r"[^A-Z0-9 ]", " ", road_name.upper()).split() if len(t) >= 3 and t not in {"ROAD", "STREET", "AVENUE", "AVE", "DRIVE", "CLOSE", "LANE"}]
    if tokens and "street_name" in out:
        mask = pd.Series(False, index=out.index)
        for t in tokens:
            mask = mask | out.street_name.str.contains(t, regex=False, na=False)
        if int(mask.sum()) >= 15:
            out = out[mask]
    if out.empty:
        return out, pd.DataFrame(), {}
    q = out.dropna(subset=["quarter", "resale_price"]).groupby("quarter", as_index=False).agg(median_price=("resale_price", "median"), transactions=("resale_price", "size"))
    max_month = out["month"].max()
    last = out[out.month >= max_month - pd.DateOffset(months=12)]
    prev = out[(out.month < max_month - pd.DateOffset(months=12)) & (out.month >= max_month - pd.DateOffset(months=24))]
    last_med = float(last.resale_price.median()) if not last.empty else None
    prev_med = float(prev.resale_price.median()) if not prev.empty else None
    yoy = round((last_med - prev_med) / prev_med * 100, 1) if last_med and prev_med else None
    return out.sort_values("month", ascending=False), q, {"latest_quarter_median": float(q.tail(1).iloc[0].median_price) if not q.empty else None, "latest_quarter_transactions": int(q.tail(1).iloc[0].transactions) if not q.empty else 0, "last_12m_median": last_med, "prior_12m_median": prev_med, "yoy_pct": yoy, "sample_size": int(len(out))}


# ----------------------------- Intelligence features -----------------------------

def score_neighbourhood(nearest_by_cat: dict[str, pd.DataFrame], bus_near: pd.DataFrame, dengue_near: pd.DataFrame, persona: str) -> dict[str, float]:
    def first(cat: str) -> float | None:
        df = nearest_by_cat.get(cat, pd.DataFrame())
        return None if df.empty else float(df.iloc[0].distance_m)
    daily = (distance_score(first("hawker_centre"), 500, 900, 2000) + distance_score(first("supermarket"), 500, 900, 2000) + distance_score(first("community_club"), 800, 1200, 2500)) / 3
    family = (distance_score(first("school"), 700, 1000, 2500) + distance_score(first("preschool"), 500, 800, 1800)) / 2
    transport = 35.0 if bus_near.empty else distance_score(float(bus_near.iloc[0].distance_m), 300, 600, 1200)
    environment = 75.0 if dengue_near.empty else max(35.0, 75.0 - min(40.0, len(dengue_near) * 10.0))
    evidence = 75.0
    weights = PERSONA_WEIGHTS[persona]
    overall = weights["transport"] * transport + weights["daily"] * daily + weights["family"] * family + weights["environment"] * environment + weights["evidence"] * evidence
    return {"overall": round(overall, 1), "transport": round(transport, 1), "daily_convenience": round(daily, 1), "family": round(family, 1), "environment": round(environment, 1), "evidence": round(evidence, 1)}


def fallback_daily_brief(profile: dict[str, Any], score: dict[str, float], weather: dict[str, Any], nearest_by_cat: dict[str, pd.DataFrame], bus_near: pd.DataFrame, dengue_near: pd.DataFrame) -> str:
    food = nearest_by_cat.get("hawker_centre", pd.DataFrame())
    grocery = nearest_by_cat.get("supermarket", pd.DataFrame())
    cc = nearest_by_cat.get("community_club", pd.DataFrame())
    parts = [f"Around **{profile['address']}**, GoAround SG gives a neighbourhood usefulness score of **{score['overall']}/100** today."]
    if weather.get("forecast"):
        parts.append(f"Nearest weather area is **{weather.get('forecast_area')}** with forecast **{weather.get('forecast')}**.")
    if not food.empty:
        parts.append(f"Food option nearby: **{food.iloc[0]['name']}** ({dist(food.iloc[0]['distance_m'])}).")
    if not grocery.empty:
        parts.append(f"Grocery option nearby: **{grocery.iloc[0]['name']}** ({dist(grocery.iloc[0]['distance_m'])}).")
    if not bus_near.empty:
        parts.append(f"Nearest bus stop: **{bus_near.iloc[0]['name']}** ({dist(bus_near.iloc[0]['distance_m'])}).")
    if not cc.empty:
        parts.append(f"Community facility nearby: **{cc.iloc[0]['name']}** ({dist(cc.iloc[0]['distance_m'])}).")
    if not dengue_near.empty:
        parts.append(f"There are **{len(dengue_near)} dengue cluster centroid(s)** within the selected radius; verify the exact NEA map before outdoor plans.")
    parts.append("Use this as a daily starting point; verify time-sensitive transport, promotions and event details at the official source.")
    return " ".join(parts)


def model_brief(prompt: str, fallback: str) -> str:
    host, token, endpoint = os.getenv("DATABRICKS_HOST"), os.getenv("DATABRICKS_TOKEN"), os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    if host and token:
        try:
            r = requests.post(f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 600}, timeout=45)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"Databricks Model Serving fallback used: {exc}\n\n{fallback}"
    return fallback


def meal_planner(profile: dict[str, Any], nearest_by_cat: dict[str, pd.DataFrame], dietary: str, budget: str) -> str:
    food = nearest_by_cat.get("hawker_centre", pd.DataFrame()).head(3)
    grocery = nearest_by_cat.get("supermarket", pd.DataFrame()).head(3)
    facts = {"address": profile["address"], "dietary": dietary, "budget": budget, "hawkers": food[["name", "distance_m"]].to_dict("records") if not food.empty else [], "supermarkets": grocery[["name", "distance_m"]].to_dict("records") if not grocery.empty else []}
    fallback = ""
    if not food.empty:
        fallback += f"**Breakfast / lunch:** Try {food.iloc[0]['name']} ({dist(food.iloc[0]['distance_m'])}) for an affordable hawker meal.\n\n"
    if len(food) > 1:
        fallback += f"**Dinner option:** Consider {food.iloc[1]['name']} ({dist(food.iloc[1]['distance_m'])}) if you want another nearby food centre.\n\n"
    if not grocery.empty:
        fallback += f"**Cook-at-home option:** Pick up ingredients from {grocery.iloc[0]['name']} ({dist(grocery.iloc[0]['distance_m'])}).\n\n"
    fallback += "Check live opening hours and promotions from the official merchant or mall pages before going."
    prompt = "Create a practical one-day meal plan for a Singapore resident using only these nearby sources. Do not invent restaurants or prices. Mention that promotions must be verified at source.\n" + str(facts)
    return model_brief(prompt, fallback)


def weekend_planner(profile: dict[str, Any], nearest_by_cat: dict[str, pd.DataFrame], weather: dict[str, Any], interests: list[str]) -> str:
    facts = {"address": profile["address"], "weather": weather, "interests": interests, "nearby": {k: v[["name", "distance_m"]].head(3).to_dict("records") for k, v in nearest_by_cat.items() if not v.empty}}
    fallback = f"**Suggested weekend plan near {profile['address']}:**\n\n"
    if weather.get("forecast"):
        fallback += f"Weather check: {weather.get('forecast_area')} is forecasted as {weather.get('forecast')}. Keep indoor backup if needed.\n\n"
    if not nearest_by_cat.get("hawker_centre", pd.DataFrame()).empty:
        fallback += f"1. Start with breakfast/lunch at {nearest_by_cat['hawker_centre'].iloc[0]['name']}.\n"
    if not nearest_by_cat.get("community_club", pd.DataFrame()).empty:
        fallback += f"2. Check activities at {nearest_by_cat['community_club'].iloc[0]['name']}.\n"
    fallback += "3. Use the events tab to check OnePA/NLB/ActiveSG official pages for this weekend's confirmed activities."
    prompt = "Create a safe, source-aware weekend plan for a Singapore resident using only the supplied nearby places and weather facts. Do not invent event names.\n" + str(facts)
    return model_brief(prompt, fallback)


def jogging_route(profile: dict[str, Any], amenities: pd.DataFrame, target_km: float) -> tuple[str, pd.DataFrame]:
    lat, lon = profile["lat"], profile["lon"]
    candidates = amenities.copy()
    if not candidates.empty:
        candidates["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in candidates.itertuples()]
        candidates = candidates[(candidates.distance_m >= 250) & (candidates.distance_m <= max(3000, target_km * 1000 / 2))].sort_values("distance_m").head(4)
    if candidates.empty:
        route = pd.DataFrame([{"name": "Start / end", "lat": lat, "lon": lon, "sequence": 1}])
        text = "No nearby open-data waypoints found for a loop. Start with a simple out-and-back route and verify safety, traffic crossings and park connectors manually."
        return text, route
    route = pd.concat([pd.DataFrame([{"name": "Start / end", "lat": lat, "lon": lon, "sequence": 1}]), candidates.assign(sequence=range(2, 2 + len(candidates)))[["name", "lat", "lon", "sequence"]], pd.DataFrame([{"name": "Return home", "lat": lat, "lon": lon, "sequence": 2 + len(candidates)}])], ignore_index=True)
    approx = 0.0
    for i in range(len(route) - 1):
        approx += haversine_m(float(route.iloc[i].lat), float(route.iloc[i].lon), float(route.iloc[i + 1].lat), float(route.iloc[i + 1].lon))
    text = f"Suggested open-data waypoint loop is approximately **{approx/1000:.1f} km**. Use this as a planning guide only; verify pedestrian paths, traffic crossings, weather and lighting before jogging."
    return text, route


@st.cache_data(ttl=3600, show_spinner=False)
def bing_search(query: str, domains: list[str] | None = None, count: int = 8) -> pd.DataFrame:
    key = os.getenv("BING_SEARCH_KEY")
    endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
    if not key:
        return pd.DataFrame()
    q = query
    if domains:
        q += " " + " OR ".join([f"site:{d}" for d in domains])
    r = requests.get(endpoint, params={"q": q, "count": count, "mkt": "en-SG", "safeSearch": "Strict"}, headers={"Ocp-Apim-Subscription-Key": key}, timeout=30)
    r.raise_for_status()
    return pd.DataFrame([{"title": item.get("name", ""), "url": item.get("url", ""), "snippet": item.get("snippet", ""), "date": item.get("dateLastCrawled", "")} for item in r.json().get("webPages", {}).get("value", [])])


# ----------------------------- UI -----------------------------

st.title("📍 GoAround SG")
st.caption("Daily neighbourhood intelligence for Singapore residents — powered by open data, location analytics and Databricks-ready AI.")

with st.sidebar:
    sample = st.selectbox("Try a block / place", ["Custom", "308C Punggol Walk", "1 Cantonment Road", "273C Punggol Place", "1 Tanjong Pagar Plaza", "83 Punggol Central"])
    address = st.text_input("My block, address or postal code", "" if sample == "Custom" else sample)
    persona = st.selectbox("Resident profile", list(PERSONA_WEIGHTS.keys()))
    radius = st.slider("Around my block radius", 500, 3000, 1500, 100)
    interests = st.multiselect("Interests", ["cheap food", "groceries", "family activities", "fitness", "community events", "transport", "safety", "shopping"], default=["cheap food", "groceries", "transport"])
    max_school_geocode = st.slider("Max schools to geocode/cache", 50, 500, 250, 50)
    max_preschool_geocode = st.slider("Max pre-schools to geocode/cache", 100, 1500, 500, 100)
    max_records = st.selectbox("HDB resale rows for buyer mode", [8000, 30000, 80000, 180000], index=1)
    if st.button("Save this block in session"):
        st.session_state["saved_block"] = address
        st.success("Saved for this session. Lakebase persistence can be enabled via LAKEBASE_DATABASE_URL.")

if not address:
    st.info("Enter your block, address or postal code to start.")
    st.stop()

try:
    profile = geocode(address)
except Exception as exc:
    st.error(f"Could not geocode with OneMap: {exc}")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Matched postal", profile["postal_code"] or "n/a")
m2.metric("Road", profile["road_name"] or "n/a")
m3.metric("Latitude", f"{profile['lat']:.5f}")
m4.metric("Longitude", f"{profile['lon']:.5f}")
st.success(f"Matched: {profile['address']}")

with st.spinner("Loading live neighbourhood data..."):
    amenities = load_live_amenities(max_school_geocode, max_preschool_geocode)
    bus_stops = load_bus_stops()
    dengue = load_dengue_clusters()
    weather = get_weather_near(profile["lat"], profile["lon"])

nearest_by_cat = {cat: nearest(amenities[amenities.category == cat], profile["lat"], profile["lon"], radius) for cat in sorted(amenities.category.dropna().unique())}
bus_near = nearest(bus_stops, profile["lat"], profile["lon"], radius, limit=6) if not bus_stops.empty else pd.DataFrame()
dengue_near = nearest(dengue, profile["lat"], profile["lon"], radius, limit=8) if not dengue.empty else pd.DataFrame()
score = score_neighbourhood(nearest_by_cat, bus_near, dengue_near, persona)

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Today", "Transport", "Meals", "Weekend", "Jogging", "Promos & events", "News & safety", "Buyer mode", "Databricks"
])

with tab1:
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Neighbourhood score")
        st.metric("Overall", f"{score['overall']}/100")
        st.progress(score["overall"] / 100)
        for k, v in score.items():
            if k != "overall":
                st.write(f"**{k.replace('_', ' ').title()}**: {v}/100")
    with right:
        st.subheader("Daily neighbourhood briefing")
        fallback = fallback_daily_brief(profile, score, weather, nearest_by_cat, bus_near, dengue_near)
        prompt = "Write a concise daily neighbourhood briefing for a Singapore resident using only these facts. Include transport, food/grocery, community, safety/environment, and what to verify.\n" + str({"profile": profile, "score": score, "weather": weather, "nearest": {k: v[["name", "distance_m"]].head(3).to_dict("records") for k, v in nearest_by_cat.items() if not v.empty}, "bus_stops": bus_near[["name", "distance_m"]].head(3).to_dict("records") if not bus_near.empty else [], "dengue_clusters": len(dengue_near), "interests": interests})
        st.markdown(model_brief(prompt, fallback))
        st.caption("Time-sensitive details should be verified with official providers before action.")
    st.subheader("Around my block map")
    rows_for_map = [v.head(8) for v in nearest_by_cat.values() if not v.empty]
    if not bus_near.empty:
        rows_for_map.append(bus_near.rename(columns={"bus_stop_code": "postal_code"}).assign(category="bus_stop").head(8))
    if rows_for_map:
        map_df = pd.concat(rows_for_map, ignore_index=True)
        fig = px.scatter_mapbox(map_df, lat="lat", lon="lon", color="category", hover_name="name", hover_data={"distance_m": ":.0f", "lat": False, "lon": False}, zoom=13, height=480)
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No mapped nearby data found within selected radius.")

with tab2:
    st.subheader("Nearby bus stops and live arrivals")
    if bus_near.empty:
        st.warning("LTA bus data is not active. Set LTA_ACCOUNT_KEY in the environment to load real bus stops and live arrivals.")
        st.markdown("Get/verify access from LTA DataMall, then set `LTA_ACCOUNT_KEY` in Databricks App environment variables.")
    else:
        b = bus_near.copy(); b["distance"] = b.distance_m.apply(dist)
        st.dataframe(b[["bus_stop_code", "name", "road_name", "distance", "source"]], use_container_width=True, hide_index=True)
        selected = st.selectbox("Check bus arrival for bus stop", b["bus_stop_code"].astype(str).tolist(), format_func=lambda code: f"{code} - {b[b.bus_stop_code.astype(str)==str(code)].iloc[0]['name']}")
        arrivals = get_bus_arrival(str(selected))
        if arrivals.empty:
            st.info("No live arrival data available for this stop right now.")
        else:
            st.dataframe(arrivals.sort_values(["service_no", "arrival_slot"]), use_container_width=True, hide_index=True)

with tab3:
    st.subheader("Meal planner around my block")
    c1, c2 = st.columns(2)
    dietary = c1.selectbox("Preference", ["No restriction", "Halal-friendly", "Vegetarian-friendly", "Kid-friendly", "Healthier choice", "Budget-first"])
    budget = c2.selectbox("Budget", ["Budget", "Moderate", "Treat myself"])
    st.markdown(meal_planner(profile, nearest_by_cat, dietary, budget))
    st.markdown("#### Promotion source links")
    for label, url in PROMOTION_SOURCES:
        st.markdown(f"- [{label}]({url})")
    st.markdown(f"- [Search nearby food deals]({google_search_link(profile['address'] + ' nearby food promotion Singapore')})")

with tab4:
    st.subheader("Weekend planner")
    st.markdown(weekend_planner(profile, nearest_by_cat, weather, interests))
    st.markdown("#### Official event sources")
    for label, url in EVENT_SOURCES:
        st.markdown(f"- [{label}]({url})")
    q = f"{profile['road_name']} {profile['postal_code']} weekend events community Singapore"
    events = bing_search(q, domains=["onepa.gov.sg", "nlb.gov.sg", "activesgcircle.gov.sg", "pa.gov.sg", "gov.sg"], count=8)
    if not events.empty:
        st.dataframe(events, use_container_width=True, hide_index=True)
    else:
        st.info("Configure BING_SEARCH_KEY to retrieve source-backed event results automatically. Manual links are shown above.")

with tab5:
    st.subheader("Jogging route planner")
    target_km = st.slider("Target route distance", 1.0, 10.0, 3.0, 0.5)
    text, route = jogging_route(profile, amenities, target_km)
    st.markdown(text)
    if len(route) > 1:
        fig = px.line_mapbox(route.sort_values("sequence"), lat="lat", lon="lon", hover_name="name", zoom=13, height=480)
        fig.add_scattermapbox(lat=route["lat"], lon=route["lon"], mode="markers", text=route["name"], marker={"size": 10})
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(route.sort_values("sequence"), use_container_width=True, hide_index=True)
    st.caption("Route is estimated from open-data waypoints, not a turn-by-turn navigation route. Verify park connectors, crossings, lighting and weather.")

with tab6:
    st.subheader("Promotions and community events")
    st.write("Promotions are fragmented across mall and merchant websites. GoAround SG uses a source registry and optional search API rather than inventing deals.")
    promo_query = f"{profile['address']} OR {profile['road_name']} promotion supermarket mall food Singapore"
    promos = bing_search(promo_query, domains=["fairprice.com.sg", "shengsiong.com.sg", "coldstorage.com.sg", "capitaland.com", "frasersproperty.com", "lendleaseplus.com"], count=8)
    if promos.empty:
        st.info("Configure BING_SEARCH_KEY for automatic promotion discovery. For now, use the official source links below.")
    else:
        st.dataframe(promos, use_container_width=True, hide_index=True)
    for label, url in PROMOTION_SOURCES + EVENT_SOURCES:
        st.markdown(f"- [{label}]({url})")

with tab7:
    st.subheader("Local news, safety and environment")
    c1, c2, c3 = st.columns(3)
    c1.metric("Weather area", weather.get("forecast_area") or "n/a")
    c2.metric("Forecast", weather.get("forecast") or "n/a")
    c3.metric("Rainfall station", weather.get("nearest_rain_station") or "n/a")
    if not dengue_near.empty:
        d = dengue_near.copy(); d["distance"] = d.distance_m.apply(dist)
        st.warning("Nearby dengue cluster centroids found. Verify exact boundaries at NEA before making decisions.")
        st.dataframe(d[["name", "locality", "case_size", "distance", "source"]], use_container_width=True, hide_index=True)
    else:
        st.success("No dengue cluster centroid found within the selected radius from the current open-data feed.")
    st.markdown("#### Credible-source local news search")
    news_query = f'"{profile["address"]}" OR "{profile["road_name"]}" Singapore community event incident update'
    news = bing_search(news_query, domains=CREDIBLE_DOMAINS, count=8)
    if news.empty:
        st.info("Configure BING_SEARCH_KEY to retrieve credible-source news results. Manual search links are provided.")
        st.markdown(f"- [Credible source search]({google_search_link(news_query + ' ' + ' OR '.join(['site:' + d for d in CREDIBLE_DOMAINS]))})")
    else:
        st.dataframe(news, use_container_width=True, hide_index=True)
    st.caption('Sensitive or incident-related content follows the rule: "No source URL = no claim."')

with tab8:
    st.subheader("Buyer / tenant mode")
    st.write("This is now a secondary mode. It uses the same neighbourhood intelligence plus HDB resale trends for people considering living in the area.")
    resale = load_hdb_resale(int(max_records))
    towns = sorted(resale.town.dropna().unique().tolist()) if not resale.empty and "town" in resale else []
    flats = sorted(resale.flat_type.dropna().unique().tolist()) if not resale.empty and "flat_type" in resale else []
    a, b = st.columns(2)
    town = a.selectbox("Town", ["Any"] + towns)
    flat = b.selectbox("Flat type", ["Any"] + flats)
    filtered, quarterly, trend = build_trend(resale, town, flat, profile.get("road_name", ""))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Latest qtr median", money(trend.get("latest_quarter_median")))
    k2.metric("Latest qtr txns", trend.get("latest_quarter_transactions", 0))
    k3.metric("Last 12m median", money(trend.get("last_12m_median")))
    k4.metric("YoY median", "n/a" if trend.get("yoy_pct") is None else f"{trend['yoy_pct']}%")
    if not quarterly.empty:
        st.plotly_chart(px.line(quarterly, x="quarter", y="median_price", markers=True, title="Median resale price by quarter"), use_container_width=True)
    if not filtered.empty:
        cols = [c for c in ["month", "town", "flat_type", "block", "street_name", "storey_range", "floor_area_sqm", "remaining_lease", "resale_price"] if c in filtered.columns]
        st.dataframe(filtered[cols].head(50), use_container_width=True, hide_index=True)

with tab9:
    st.subheader("Databricks implementation")
    st.code("""Open data + APIs
  -> Databricks Jobs / notebooks
  -> Bronze raw Delta tables
  -> Silver cleaned location and event tables
  -> Gold resident_daily_feed, nearby_transport, promotions, evidence, buyer_features
  -> Databricks App: GoAround SG
  -> Genie: natural-language neighbourhood questions
  -> Model Serving: daily briefing, meal planner, weekend planner
  -> Lakebase: saved block, preferences, watchlist, alert state""", language="text")
    st.markdown("#### Ask GoAround examples for Genie / AI")
    examples = [
        "What is useful around my block today?",
        "Which nearby bus stop should I use?",
        "Plan a budget meal day near my block.",
        "What can I do with my child this weekend near this estate?",
        "Any credible local news or official updates around my block?",
        "Is this area suitable for a car-free resident?",
    ]
    for e in examples:
        st.markdown(f"- {e}")
    ask = st.text_input("Ask GoAround", placeholder="e.g. What should I do near my block this weekend?")
    if ask:
        facts = {"question": ask, "profile": profile, "score": score, "weather": weather, "nearest": {k: v[["name", "distance_m"]].head(3).to_dict("records") for k, v in nearest_by_cat.items() if not v.empty}, "bus_stops": bus_near[["name", "distance_m"]].head(3).to_dict("records") if not bus_near.empty else []}
        fallback = "Based on the current open-data context, check the Today, Transport, Meals, Weekend, Promos & events, and News & safety tabs for source-backed details. Configure Databricks Model Serving for richer natural-language answers."
        st.markdown(model_brief("Answer the resident's question using only these facts. Be practical and source-aware.\n" + str(facts), fallback))

st.caption("GoAround SG is a hackathon prototype. It does not replace official transport, weather, safety, medical, legal, financial or valuation advice.")
