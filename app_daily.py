from __future__ import annotations

import math
import os
import re
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
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
RAINFALL_URL = "https://api.data.gov.sg/v1/environment/rainfall"
LTA_BUS_STOPS_URL = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"

DATASETS = {
    "hdb_resale": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",
    "hawker_centres": "d_4a086da0a5553be1d89383cd90d07ecd",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
    "schools": "d_688b934f82c1059ed0a6993d2a829089",
    "preschools": "d_696c994c50745b079b3684f0e90ffc53",
}

CREDIBLE_DOMAINS = [
    "channelnewsasia.com", "straitstimes.com", "todayonline.com", "mothership.sg",
    "gov.sg", "hdb.gov.sg", "lta.gov.sg", "ura.gov.sg", "scdf.gov.sg", "police.gov.sg",
]

PROMO_SOURCES = [
    {"name": "FairPrice promotions", "url": "https://www.fairprice.com.sg/promotions", "category": "Groceries"},
    {"name": "Sheng Siong promotions", "url": "https://shengsiong.com.sg/promotions", "category": "Groceries"},
    {"name": "Cold Storage promotions", "url": "https://coldstorage.com.sg/promotions", "category": "Groceries"},
    {"name": "CapitaLand mall promotions", "url": "https://www.capitaland.com/sg/malls/promotions.html", "category": "Mall"},
    {"name": "Frasers Property mall promotions", "url": "https://www.frasersproperty.com/sg/malls/promotions", "category": "Mall"},
    {"name": "Lendlease Plus promotions", "url": "https://www.lendleaseplus.com/sg/en/promotions.html", "category": "Mall"},
]

EVENT_SOURCES = [
    {"name": "OnePA events", "url": "https://www.onepa.gov.sg/events", "category": "Community"},
    {"name": "NLB events", "url": "https://www.nlb.gov.sg/main/whats-on/events", "category": "Family / learning"},
    {"name": "ActiveSG activities", "url": "https://www.activesgcircle.gov.sg/", "category": "Fitness"},
    {"name": "HDB press releases", "url": "https://www.hdb.gov.sg/about-us/news-and-publications/press-releases", "category": "Estate updates"},
    {"name": "LTA upcoming projects", "url": "https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html", "category": "Transport"},
    {"name": "URA Draft Master Plan", "url": "https://www.uradraftmasterplan.gov.sg/", "category": "Future plans"},
]

# ----------------------------- helpers -----------------------------

def api_headers() -> dict[str, str]:
    h = {"User-Agent": "goaround-sg-daily/0.1"}
    if os.getenv("DATA_GOV_API_KEY"):
        h["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return h


def lta_headers() -> dict[str, str]:
    return {"AccountKey": os.getenv("LTA_ACCOUNT_KEY", ""), "accept": "application/json"}


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in out.columns]
    return out.drop(columns=["_id"], errors="ignore")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dist(v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    v = float(v)
    return f"{v:,.0f} m" if v < 1000 else f"{v/1000:.1f} km"


def google_link(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)


def source_domain_filter(domains: list[str]) -> str:
    return " OR ".join([f"site:{d}" for d in domains])


# ----------------------------- source loading -----------------------------

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
def poll_download_url(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=api_headers(), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=30)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {
        "address": best.get("ADDRESS") or query,
        "building": best.get("BUILDING") or "",
        "postal_code": best.get("POSTAL") or "",
        "road_name": best.get("ROAD_NAME") or "",
        "lat": float(best["LATITUDE"]),
        "lon": float(best["LONGITUDE"]),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    try:
        gj = requests.get(poll_download_url(dataset_id), headers=api_headers(), timeout=90).json()
        rows = []
        for f in gj.get("features", []):
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates") or []
            props = f.get("properties") or {}
            if geom.get("type") == "Point" and len(coords) >= 2:
                name = props.get("NAME") or props.get("Name") or props.get("ADDRESSBUILDINGNAME") or props.get("DESCRIPTION") or category
                address = " ".join([
                    str(props.get("ADDRESSBLOCKHOUSENUMBER") or ""),
                    str(props.get("ADDRESSSTREETNAME") or ""),
                ]).strip() or str(props.get("ADDRESS") or "")
                rows.append({
                    "category": category, "name": str(name), "address": address,
                    "postal_code": str(props.get("ADDRESSPOSTALCODE") or ""),
                    "lat": float(coords[1]), "lon": float(coords[0]), "source": "data.gov.sg",
                })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=False)
def load_named_records(dataset_id: str, category: str, max_geocode: int, name_candidates: list[str], address_candidates: list[str], postal_candidates: list[str]) -> pd.DataFrame:
    df = datastore_search(dataset_id, max_records=max_geocode)
    if df.empty:
        return pd.DataFrame()
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "lng"] if c in df.columns), None)
    name_col = next((c for c in name_candidates if c in df.columns), None)
    address_col = next((c for c in address_candidates if c in df.columns), None)
    postal_col = next((c for c in postal_candidates if c in df.columns), None)
    if lat_col and lon_col and name_col:
        return pd.DataFrame({
            "category": category,
            "name": df[name_col].astype(str),
            "address": df[address_col].astype(str) if address_col else "",
            "postal_code": df[postal_col].astype(str) if postal_col else "",
            "lat": pd.to_numeric(df[lat_col], errors="coerce"),
            "lon": pd.to_numeric(df[lon_col], errors="coerce"),
            "source": "data.gov.sg",
        }).dropna(subset=["lat", "lon"])
    rows = []
    for _, row in df.head(max_geocode).iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        address = str(row.get(address_col, "")).strip() if address_col else ""
        postal = str(row.get(postal_col, "")).strip() if postal_col else ""
        query = postal or address or name
        if not query:
            continue
        try:
            g = geocode(query)
            rows.append({"category": category, "name": name or g.get("building") or query, "address": address or g["address"], "postal_code": postal or g.get("postal_code", ""), "lat": g["lat"], "lon": g["lon"], "source": "data.gov.sg + OneMap geocode"})
        except Exception:
            continue
    return pd.DataFrame(rows)


@st.cache_data(ttl=86400, show_spinner=True)
def load_daily_neighbourhood_data(max_school: int = 160, max_preschool: int = 250) -> pd.DataFrame:
    frames = [
        load_geojson_points(DATASETS["hawker_centres"], "food"),
        load_geojson_points(DATASETS["supermarkets"], "grocery"),
        load_geojson_points(DATASETS["community_clubs"], "community"),
        load_named_records(DATASETS["schools"], "school", max_school, ["school_name", "name"], ["address", "school_address"], ["postal_code", "postal"]),
        load_named_records(DATASETS["preschools"], "preschool", max_preschool, ["centre_name", "center_name", "name"], ["centre_address", "address"], ["postal_code", "postal"]),
    ]
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])
    out = pd.concat(frames, ignore_index=True)
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["lat", "lon"]).drop_duplicates(["category", "name", "lat", "lon"])


@st.cache_data(ttl=1800, show_spinner=False)
def get_weather_near(lat: float, lon: float) -> dict[str, Any]:
    out = {"forecast_area": None, "forecast": None, "rain_station": None, "rainfall_mm": None}
    try:
        data = requests.get(WEATHER_2H_URL, timeout=20).json()
        forecasts = {x["area"]: x.get("forecast") for x in data.get("items", [{}])[0].get("forecasts", [])}
        best = None
        for area in data.get("area_metadata", []):
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
        data = requests.get(RAINFALL_URL, timeout=20).json()
        stations = {s["id"]: s for s in data.get("metadata", {}).get("stations", [])}
        best = None
        for reading in data.get("items", [{}])[0].get("readings", []):
            stn = stations.get(reading.get("station_id"))
            if not stn:
                continue
            loc = stn.get("location") or {}
            d = haversine_m(lat, lon, float(loc.get("latitude")), float(loc.get("longitude")))
            if best is None or d < best[0]:
                best = (d, stn.get("name"), reading.get("value"))
        if best:
            out["rain_station"] = best[1]
            out["rainfall_mm"] = best[2]
    except Exception:
        pass
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def load_bus_stops(max_pages: int = 12) -> pd.DataFrame:
    if not os.getenv("LTA_ACCOUNT_KEY"):
        return pd.DataFrame()
    rows = []
    for page in range(max_pages):
        r = requests.get(LTA_BUS_STOPS_URL, params={"$skip": page * 500}, headers=lta_headers(), timeout=30)
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
def get_bus_arrivals(bus_stop_code: str) -> pd.DataFrame:
    if not os.getenv("LTA_ACCOUNT_KEY") or not bus_stop_code:
        return pd.DataFrame()
    r = requests.get(LTA_BUS_ARRIVAL_URL, params={"BusStopCode": bus_stop_code}, headers=lta_headers(), timeout=30)
    r.raise_for_status()
    now = datetime.now().astimezone()
    rows = []
    for svc in r.json().get("Services", []):
        arrivals = []
        for key in ["NextBus", "NextBus2", "NextBus3"]:
            eta = (svc.get(key) or {}).get("EstimatedArrival")
            if not eta:
                arrivals.append(None)
                continue
            try:
                eta_dt = datetime.fromisoformat(eta.replace("Z", "+00:00")).astimezone()
                arrivals.append(max(0, int((eta_dt - now).total_seconds() // 60)))
            except Exception:
                arrivals.append(None)
        rows.append({"service_no": svc.get("ServiceNo"), "operator": svc.get("Operator"), "next_min": arrivals[0], "next_2_min": arrivals[1], "next_3_min": arrivals[2]})
    return pd.DataFrame(rows)


def nearest(df: pd.DataFrame, lat: float, lon: float, radius_m: int, limit: int = 12) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.dropna(subset=["lat", "lon"]).copy()
    out["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in out.itertuples()]
    return out[out.distance_m <= radius_m].sort_values("distance_m").head(limit)


@st.cache_data(ttl=3600, show_spinner=False)
def bing_search(query: str, domains: list[str] | None = None) -> pd.DataFrame:
    key = os.getenv("BING_SEARCH_KEY")
    if not key:
        return pd.DataFrame()
    q = query + (" " + source_domain_filter(domains) if domains else "")
    r = requests.get(os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"), params={"q": q, "count": 8, "mkt": "en-SG", "safeSearch": "Strict"}, headers={"Ocp-Apim-Subscription-Key": key}, timeout=30)
    r.raise_for_status()
    return pd.DataFrame([{"title": x.get("name", ""), "url": x.get("url", ""), "snippet": x.get("snippet", ""), "date": x.get("dateLastCrawled", "")} for x in r.json().get("webPages", {}).get("value", [])])


# ----------------------------- Memory -----------------------------

def save_profile_to_session(address: str, radius: int, interests: list[str], fav_bus_stop: str | None = None) -> None:
    st.session_state["goaround_profile"] = {"address": address, "radius": radius, "interests": interests, "fav_bus_stop": fav_bus_stop, "saved_at": datetime.now().isoformat(timespec="seconds")}


def render_memory_status() -> None:
    profile = st.session_state.get("goaround_profile")
    if profile:
        st.success(f"Saved block: {profile['address']} · radius {profile['radius']}m · interests: {', '.join(profile['interests'])}")
    else:
        st.info("Save your block once to make this a daily app. Lakebase persistence can replace session memory for production.")


# ----------------------------- Intelligence -----------------------------

def simple_score(near: dict[str, pd.DataFrame], bus_near: pd.DataFrame) -> dict[str, float]:
    def score_dist(cat: str, good: int, maxd: int) -> float:
        df = near.get(cat, pd.DataFrame())
        if df.empty:
            return 35.0
        d = float(df.iloc[0].distance_m)
        if d <= good:
            return 100.0
        if d <= maxd:
            return max(30.0, 100 - (d - good) / (maxd - good) * 70)
        return 20.0
    transport = 35.0 if bus_near.empty else score_dist_bus(float(bus_near.iloc[0].distance_m))
    food = score_dist("food", 700, 1800)
    grocery = score_dist("grocery", 700, 1800)
    community = score_dist("community", 1000, 2500)
    family = (score_dist("school", 1000, 2500) + score_dist("preschool", 800, 1800)) / 2
    everyday = 0.35 * transport + 0.25 * food + 0.20 * grocery + 0.10 * community + 0.10 * family
    return {"overall": round(everyday, 1), "transport": round(transport, 1), "food": round(food, 1), "grocery": round(grocery, 1), "community": round(community, 1), "family": round(family, 1)}


def score_dist_bus(d: float) -> float:
    if d <= 300:
        return 100.0
    if d <= 700:
        return 80.0
    if d <= 1200:
        return 50.0
    return 25.0


def daily_brief(profile: dict[str, Any], score: dict[str, float], weather: dict[str, Any], near: dict[str, pd.DataFrame], bus_near: pd.DataFrame, arrivals: pd.DataFrame) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    if not bus_near.empty:
        bus = bus_near.iloc[0]
        if not arrivals.empty and pd.notna(arrivals.iloc[0].get("next_min")):
            detail = f"{bus['name']} is {dist(bus.distance_m)} away. Bus {arrivals.iloc[0]['service_no']} arrives in about {int(arrivals.iloc[0]['next_min'])} min."
        else:
            detail = f"{bus['name']} is {dist(bus.distance_m)} away. Open Transport tab for live arrivals."
        cards.append({"title": "🚌 Transport now", "body": detail, "action": "Check favourite bus services before leaving."})
    else:
        cards.append({"title": "🚌 Transport now", "body": "Set LTA_ACCOUNT_KEY to enable nearby bus stops and live arrival times.", "action": "For demo, configure LTA DataMall key."})

    if weather.get("forecast"):
        rain = f" Rainfall near {weather.get('rain_station')}: {weather.get('rainfall_mm')} mm." if weather.get("rain_station") else ""
        cards.append({"title": "🌦 Weather", "body": f"{weather.get('forecast_area')}: {weather.get('forecast')}.{rain}", "action": "Carry umbrella if rain looks likely."})

    food = near.get("food", pd.DataFrame())
    grocery = near.get("grocery", pd.DataFrame())
    if not food.empty:
        cards.append({"title": "🍜 Meal idea", "body": f"Nearest hawker/food option: {food.iloc[0]['name']} ({dist(food.iloc[0].distance_m)}).", "action": "Use Deals & Events for promotion links."})
    if not grocery.empty:
        cards.append({"title": "🛒 Grocery", "body": f"Nearest supermarket: {grocery.iloc[0]['name']} ({dist(grocery.iloc[0].distance_m)}).", "action": "Check FairPrice/Sheng Siong/Cold Storage promo pages."})

    community = near.get("community", pd.DataFrame())
    if not community.empty:
        cards.append({"title": "🏘 Community", "body": f"Nearby community facility: {community.iloc[0]['name']} ({dist(community.iloc[0].distance_m)}).", "action": "Check OnePA/NLB/ActiveSG for weekend activities."})

    cards.append({"title": "🛡 Local updates", "body": "Sensitive news or incidents are never inferred. GoAround only shows credible-source results or manual source links.", "action": "No source URL = no claim."})
    return cards


def answer_with_model(question: str, facts: dict[str, Any], fallback: str) -> str:
    host, token, endpoint = os.getenv("DATABRICKS_HOST"), os.getenv("DATABRICKS_TOKEN"), os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    if not (host and token):
        return fallback
    try:
        prompt = "Answer as GoAround SG, a Singapore resident daily neighbourhood assistant. Use only these facts. Be practical, short, source-aware, and do not invent promotions/events/incidents.\n" + str({"question": question, "facts": facts})
        r = requests.post(f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 450}, timeout=45)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"Databricks Model Serving fallback used: {exc}\n\n{fallback}"


# ----------------------------- UI -----------------------------

st.title("📍 GoAround SG")
st.caption("Your daily neighbourhood briefing around your block — transport, meals, deals, events, local updates and Ask GoAround.")

with st.sidebar:
    st.header("My block")
    saved = st.session_state.get("goaround_profile", {})
    sample = st.selectbox("Try a block", ["Custom", "308C Punggol Walk", "83 Punggol Central", "1 Cantonment Road", "1 Tanjong Pagar Plaza"])
    default_address = saved.get("address", "") if sample == "Custom" else sample
    address = st.text_input("Block / address / postal code", default_address)
    radius = st.slider("Daily radius", 500, 2500, int(saved.get("radius", 1200)), 100)
    interests = st.multiselect("What I care about", ["transport", "cheap food", "groceries", "family activities", "fitness", "events", "local news", "buyer mode"], default=saved.get("interests", ["transport", "cheap food", "groceries"]))
    max_school = st.slider("School geocode limit", 50, 400, 120, 50)
    max_preschool = st.slider("Pre-school geocode limit", 50, 800, 180, 50)
    if st.button("Save my block"):
        save_profile_to_session(address, radius, interests)

render_memory_status()

if not address:
    st.stop()

try:
    profile = geocode(address)
except Exception as exc:
    st.error(f"Could not locate this address with OneMap: {exc}")
    st.stop()

with st.spinner("Preparing today's neighbourhood feed..."):
    amenities = load_daily_neighbourhood_data(max_school, max_preschool)
    bus_stops = load_bus_stops()
    weather = get_weather_near(profile["lat"], profile["lon"])

near = {cat: nearest(amenities[amenities.category == cat], profile["lat"], profile["lon"], radius, 8) for cat in sorted(amenities.category.dropna().unique())}
bus_near = nearest(bus_stops, profile["lat"], profile["lon"], radius, 6) if not bus_stops.empty else pd.DataFrame()
arrivals = get_bus_arrivals(str(bus_near.iloc[0].bus_stop_code)) if not bus_near.empty else pd.DataFrame()
score = simple_score(near, bus_near)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Matched postal", profile.get("postal_code") or "n/a")
m2.metric("Everyday score", f"{score['overall']}/100")
m3.metric("Weather", weather.get("forecast") or "n/a")
m4.metric("Nearest bus", "n/a" if bus_near.empty else dist(bus_near.iloc[0].distance_m))

# fewer, habit-oriented tabs
tab_today, tab_transport, tab_deals, tab_ask, tab_more = st.tabs(["Today", "Transport", "Deals & Events", "Ask GoAround", "More"])

with tab_today:
    st.subheader("Today around my block")
    st.caption(f"{profile['address']} · {radius}m radius · updated {datetime.now().strftime('%d %b %Y, %H:%M')}")
    cards = daily_brief(profile, score, weather, near, bus_near, arrivals)
    for idx in range(0, len(cards), 2):
        cols = st.columns(2)
        for col, card in zip(cols, cards[idx: idx + 2]):
            with col:
                st.markdown(f"### {card['title']}")
                st.write(card["body"])
                st.info(card["action"])
    st.subheader("Map around my block")
    rows = [df.head(6) for df in near.values() if not df.empty]
    if not bus_near.empty:
        rows.append(bus_near.assign(address=bus_near["road_name"], postal_code=bus_near["bus_stop_code"]).head(6))
    if rows:
        map_df = pd.concat(rows, ignore_index=True)
        fig = px.scatter_mapbox(map_df, lat="lat", lon="lon", color="category", hover_name="name", hover_data={"distance_m": ":.0f", "lat": False, "lon": False}, zoom=13, height=480)
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

with tab_transport:
    st.subheader("Transport now")
    if bus_near.empty:
        st.warning("Live bus data is not enabled. Add `LTA_ACCOUNT_KEY` in Databricks App environment variables.")
    else:
        b = bus_near.copy()
        b["distance"] = b.distance_m.apply(dist)
        st.dataframe(b[["bus_stop_code", "name", "road_name", "distance", "source"]], use_container_width=True, hide_index=True)
        selected = st.selectbox("Favourite / current bus stop", b["bus_stop_code"].astype(str).tolist(), format_func=lambda x: f"{x} - {b[b.bus_stop_code.astype(str)==str(x)].iloc[0]['name']}")
        if st.button("Save favourite bus stop"):
            save_profile_to_session(address, radius, interests, selected)
        arr = get_bus_arrivals(selected)
        if arr.empty:
            st.info("No arrival estimates available right now.")
        else:
            st.dataframe(arr.sort_values(["service_no"]), use_container_width=True, hide_index=True)

with tab_deals:
    st.subheader("Deals & Events near me")
    st.caption("GoAround does not invent promotions/events. It either shows official source links or source-backed search results when a search key is configured.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🛒 Deals to check today")
        q = f"{profile['road_name']} {profile['postal_code']} supermarket mall food promotion Singapore"
        results = bing_search(q, ["fairprice.com.sg", "shengsiong.com.sg", "coldstorage.com.sg", "capitaland.com", "frasersproperty.com", "lendleaseplus.com"])
        if results.empty:
            for src in PROMO_SOURCES:
                st.markdown(f"- [{src['name']}]({src['url']}) · {src['category']}")
            st.markdown(f"- [Search deals around this block]({google_link(q)})")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("### 🎟 Events this week")
        q = f"{profile['road_name']} {profile['postal_code']} community event weekend Singapore"
        results = bing_search(q, ["onepa.gov.sg", "nlb.gov.sg", "activesgcircle.gov.sg", "pa.gov.sg", "hdb.gov.sg", "lta.gov.sg"])
        if results.empty:
            for src in EVENT_SOURCES:
                st.markdown(f"- [{src['name']}]({src['url']}) · {src['category']}")
            st.markdown(f"- [Search events around this block]({google_link(q)})")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)

    st.markdown("### 🍜 Quick meal plan")
    food = near.get("food", pd.DataFrame())
    grocery = near.get("grocery", pd.DataFrame())
    meal_plan = []
    if not food.empty:
        meal_plan.append(f"Breakfast/lunch: {food.iloc[0]['name']} ({dist(food.iloc[0].distance_m)})")
    if len(food) > 1:
        meal_plan.append(f"Dinner outside: {food.iloc[1]['name']} ({dist(food.iloc[1].distance_m)})")
    if not grocery.empty:
        meal_plan.append(f"Cook-at-home backup: buy ingredients from {grocery.iloc[0]['name']} ({dist(grocery.iloc[0].distance_m)})")
    if meal_plan:
        for item in meal_plan:
            st.success(item)
    else:
        st.info("No food/grocery open-data source found within selected radius.")

with tab_ask:
    st.subheader("Ask GoAround")
    st.caption("Natural-language layer for the daily resident workflow. Uses Databricks Model Serving when configured; otherwise returns a grounded fallback.")
    suggestions = [
        "What is useful around my block today?",
        "Which bus stop should I use now?",
        "Plan a cheap meal day near me.",
        "What can I do this weekend nearby?",
        "Any source-backed local updates around my estate?",
    ]
    st.write("Try asking:")
    for s in suggestions:
        st.markdown(f"- {s}")
    question = st.text_input("Your question")
    if question:
        facts = {
            "address": profile,
            "score": score,
            "weather": weather,
            "nearest": {k: v[["name", "distance_m"]].head(3).to_dict("records") for k, v in near.items() if not v.empty},
            "bus_stops": bus_near[["bus_stop_code", "name", "distance_m"]].head(3).to_dict("records") if not bus_near.empty else [],
            "interests": interests,
        }
        fallback = "Based on available open data: check the Today tab for your daily briefing, Transport for live buses if LTA key is enabled, and Deals & Events for source-backed promotion/event links. I will not invent promotions, incidents or events without a source."
        st.markdown(answer_with_model(question, facts, fallback))

with tab_more:
    st.subheader("More: buyer mode and Databricks architecture")
    with st.expander("Buyer / tenant mode", expanded=False):
        st.write("Buyer mode is secondary. It can be enabled for resale comparables and area evaluation, but it is no longer the main app experience.")
        if "buyer mode" in interests:
            resale = datastore_search(DATASETS["hdb_resale"], max_records=30000)
            if not resale.empty:
                resale["month"] = pd.to_datetime(resale["month"], errors="coerce")
                resale["resale_price"] = pd.to_numeric(resale["resale_price"], errors="coerce")
                resale["quarter"] = resale["month"].dt.to_period("Q").astype(str)
                for c in ["town", "flat_type", "street_name"]:
                    if c in resale.columns:
                        resale[c] = resale[c].astype(str).str.upper().str.strip()
                towns = ["Any"] + sorted(resale.town.dropna().unique().tolist())
                flats = ["Any"] + sorted(resale.flat_type.dropna().unique().tolist())
                t, f = st.columns(2)
                town = t.selectbox("Town", towns)
                flat = f.selectbox("Flat type", flats)
                comp = resale.copy()
                if town != "Any": comp = comp[comp.town == town]
                if flat != "Any": comp = comp[comp.flat_type == flat]
                q = comp.groupby("quarter", as_index=False).agg(median_price=("resale_price", "median"), transactions=("resale_price", "size"))
                if not q.empty:
                    st.plotly_chart(px.line(q, x="quarter", y="median_price", markers=True), use_container_width=True)
                st.dataframe(comp.sort_values("month", ascending=False).head(30), use_container_width=True, hide_index=True)
            else:
                st.info("HDB resale data not loaded.")
        else:
            st.info("Select 'buyer mode' in sidebar interests to load resale analytics.")
    with st.expander("Databricks usage", expanded=True):
        st.code("""Databricks Apps: deploy GoAround SG as the resident-facing app
Lakehouse / Delta: Bronze/Silver/Gold open-data tables for amenities, transport, deals, events and buyer mode
Genie: natural-language neighbourhood questions
Model Serving: Ask GoAround and daily briefing generation
Lakebase: saved block, favourite bus stop, interests, watchlist and alert state
Jobs / Workflows: daily refresh of open data, promos, events and source-backed updates""", language="text")

st.caption("GoAround SG prototype. Verify transport, promotions, events, weather and safety information with official sources before acting.")
