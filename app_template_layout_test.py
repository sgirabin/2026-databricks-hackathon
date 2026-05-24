from __future__ import annotations

import math
import os
from html import escape
from typing import Any
from urllib.parse import urlencode
from datetime import datetime

import requests
import streamlit as st

try:
    from streamlit_js_eval import get_geolocation, streamlit_js_eval
except Exception:  # pragma: no cover - keeps local/dev startup safe if package is missing
    get_geolocation = None
    streamlit_js_eval = None

st.set_page_config(
    page_title="GoAround SG - Hyperlocal Discovery",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# GoAround SG imports
from src.goaround.models import UserContext, PickCard, RankedPick
from src.goaround.ranking import rank_cards, infer_time_of_day
from src.goaround.seed_data import source_registry_cards, area_anchor_cards
from src.goaround.business import (
    create_business_promo_card,
    load_business_promotions,
    save_business_promotion,
)
from src.goaround.agent import answer_with_databricks

DEFAULT_LOCATION = "Singapore"
DEFAULT_COORDS = "1.3521, 103.8198"
DEFAULT_RADIUS_M = 1500
GEOLOCATION_KEY = "goaround_auto_geolocation"
IP_LOCATION_KEY = "goaround_ip_location"
DEFAULT_SQL_HOST = "dbc-68521f65-774f.cloud.databricks.com"
DEFAULT_SQL_HTTP_PATH = "/sql/1.0/warehouses/e3ab5c87926da4b9"

KNOWN_AREAS = [
    ("Sengkang, Singapore", 1.3871, 103.8915),
    ("Punggol, Singapore", 1.4052, 103.9023),
    ("Chinatown, Singapore", 1.2844, 103.8435),
    ("Orchard, Singapore", 1.3048, 103.8318),
    ("City Hall, Singapore", 1.2931, 103.8521),
    ("Tampines, Singapore", 1.3496, 103.9568),
    ("Jurong East, Singapore", 1.3331, 103.7423),
]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_area(lat: float, lon: float) -> str:
    name, _, _ = min(KNOWN_AREAS, key=lambda item: distance_km(lat, lon, item[1], item[2]))
    return name


def parse_coords(value: str) -> tuple[float, float] | None:
    try:
        lat_s, lon_s = value.split(",", 1)
        return float(lat_s.strip()), float(lon_s.strip())
    except Exception:
        return None


def extract_geolocation_coords(value: object) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    coords = value.get("coords")
    if not isinstance(coords, dict):
        wrapped = value.get("value")
        if isinstance(wrapped, dict):
            coords = wrapped.get("coords")
    if not isinstance(coords, dict):
        return None
    lat_value = coords.get("latitude")
    lon_value = coords.get("longitude")
    if lat_value is None or lon_value is None:
        return None
    try:
        return float(lat_value), float(lon_value)
    except (TypeError, ValueError):
        return None


def extract_geolocation_error(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    error = value.get("error")
    if not isinstance(error, dict):
        wrapped = value.get("value")
        if isinstance(wrapped, dict):
            error = wrapped.get("error")
    if not isinstance(error, dict):
        return None
    return str(error.get("message") or "Browser location is unavailable.")


def extract_ip_location_coords(value: object) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    data = value.get("value")
    if not isinstance(data, dict):
        data = value
    lat_value = data.get("latitude", data.get("lat"))
    lon_value = data.get("longitude", data.get("lon"))
    if lat_value is None or lon_value is None:
        return None
    try:
        return float(lat_value), float(lon_value)
    except (TypeError, ValueError):
        return None


def apply_detected_location(
    *,
    detected_lat: float,
    detected_lon: float,
    detected_source: str,
    current_page: str,
) -> None:
    coords_value = f"{detected_lat:.4f}, {detected_lon:.4f}"
    location_value = nearest_area(detected_lat, detected_lon)
    st.session_state["location"] = location_value
    st.session_state["coords"] = coords_value
    st.session_state["location_source"] = detected_source
    st.query_params.update(
        {
            "page": current_page,
            "location": location_value,
            "coords": coords_value,
            "source": detected_source,
        }
    )
    st.rerun()


def weather_icon(forecast: str) -> str:
    text = forecast.lower()
    if "thunder" in text:
        return "⛈️"
    if "shower" in text or "rain" in text:
        return "🌧️"
    if "cloud" in text:
        return "⛅"
    if "fair" in text or "sun" in text:
        return "☀️"
    return "🌤️"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_weather(lat: float, lon: float) -> dict[str, str]:
    fallback = {
        "forecast": "Partly Cloudy (Day)",
        "temperature": "35°C",
        "source": "Weather fallback",
        "icon": "⛅",
    }
    try:
        forecast_res = requests.get(
            "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast",
            timeout=3,
        )
        forecast_res.raise_for_status()
        forecast_data = forecast_res.json()
        metadata = forecast_data.get("area_metadata", [])
        nearest_name = None
        if metadata:
            nearest = min(
                metadata,
                key=lambda item: distance_km(
                    lat,
                    lon,
                    item.get("label_location", {}).get("latitude", lat),
                    item.get("label_location", {}).get("longitude", lon),
                ),
            )
            nearest_name = nearest.get("name")
        forecast = fallback["forecast"]
        if nearest_name:
            for item in forecast_data.get("items", [{}])[0].get("forecasts", []):
                if item.get("area") == nearest_name:
                    forecast = item.get("forecast", forecast)
                    break

        temperature = fallback["temperature"]
        try:
            temp_res = requests.get("https://api.data.gov.sg/v1/environment/air-temperature", timeout=3)
            temp_res.raise_for_status()
            temp_data = temp_res.json()
            station_map = {
                station["id"]: station["location"] for station in temp_data.get("metadata", {}).get("stations", [])
            }
            readings = temp_data.get("items", [{}])[0].get("readings", [])
            if readings:
                nearest_reading = min(
                    readings,
                    key=lambda reading: distance_km(
                        lat,
                        lon,
                        station_map.get(reading.get("station_id"), {}).get("latitude", lat),
                        station_map.get(reading.get("station_id"), {}).get("longitude", lon),
                    ),
                )
                temperature = f"{round(float(nearest_reading.get('value')))}°C"
        except Exception:
            pass

        return {
            "forecast": forecast,
            "temperature": temperature,
            "source": "data.gov.sg Weather API",
            "icon": weather_icon(forecast),
        }
    except Exception:
        return fallback


def source_icon(card_type: str, category: str) -> str:
    text = f"{card_type} {category}".lower()
    if "food" in text or "hawker" in text:
        return "🍴"
    if "grocery" in text or "deal" in text:
        return "🛒"
    if "transport" in text:
        return "🚌"
    if "park" in text:
        return "🌳"
    if "family" in text:
        return "👨‍👩‍👧"
    if "health" in text:
        return "🏥"
    if "tourist" in text:
        return "🧭"
    if "recycling" in text:
        return "♻️"
    if "fitness" in text:
        return "🏃"
    if "community" in text or "event" in text:
        return "📅"
    return "📍"


def distance_label(distance_m: float | None) -> str:
    if distance_m is None:
        return "Singapore source"
    if distance_m < 1000:
        return f"{distance_m:.0f}m away"
    return f"{distance_m / 1000:.1f}km away"


def normalized_url(url: str) -> str:
    if not url:
        return "https://data.gov.sg/"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://" + url


def databricks_sql_settings() -> tuple[str | None, str | None, str | None, str, str]:
    raw_host = os.getenv("DATABRICKS_SERVER_HOSTNAME") or os.getenv("DATABRICKS_HOST") or DEFAULT_SQL_HOST
    host = raw_host.replace("https://", "").replace("http://", "").strip("/")
    http_path = os.getenv("DATABRICKS_HTTP_PATH") or DEFAULT_SQL_HTTP_PATH
    token = os.getenv("DATABRICKS_TOKEN")
    catalog = os.getenv("GOAROUND_CATALOG", "workspace")
    if catalog == "goaround_sg":
        catalog = "workspace"
    schema = os.getenv("GOAROUND_SCHEMA", "goaround_sg")
    return host, http_path, token, catalog, schema


@st.cache_data(ttl=300, show_spinner=False)
def load_nearby_databricks_picks(user_lat: float, user_lon: float, limit: int = 160) -> tuple[list[PickCard], str]:
    host, http_path, token, catalog, schema = databricks_sql_settings()
    if not token:
        return [], "Databricks token is not configured"
    try:
        from databricks import sql
    except Exception as exc:
        return [], f"Databricks SQL connector unavailable: {exc}"

    table = f"{catalog}.{schema}.gold_candidate_cards"
    lat_sql = float(user_lat)
    lon_sql = float(user_lon)
    distance_sql = (
        f"SQRT(POWER((lat - {lat_sql}) * 111320, 2) + "
        f"POWER((lon - {lon_sql}) * 111320 * COS(RADIANS({lat_sql})), 2))"
    )
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
          source_reliability,
          {distance_sql} AS distance_m
        FROM {table}
        WHERE source_url IS NOT NULL
          AND lat IS NOT NULL
          AND lon IS NOT NULL
        ORDER BY distance_m ASC
        LIMIT {int(limit)}
    """
    try:
        with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            cursor.close()
            
        cards = []
        for idx, r in enumerate(rows):
            title = r.get("title") or r.get("category") or "Local Update"
            # Clean up cryptic geo-tags (like 'kml_22') to make them beautiful for end-users
            if title.startswith("kml_") or title.startswith("KML_"):
                src_name = r.get("source_name") or "Public Registry"
                title = f"{src_name} Facility ({title.upper()})"
                
            cards.append(PickCard(
                id=f"sql-{idx}-{abs(hash(title)) % 100000}",
                card_type=r.get("card_type") or "local_update",
                title=title,
                description=r.get("description") or "Local area update.",
                source_name=r.get("source_name") or "Databricks Delta Lake",
                source_url=r.get("source_url") or "https://data.gov.sg/",
                category=r.get("category") or "local",
                lat=None if r.get("lat") is None else float(r["lat"]),
                lon=None if r.get("lon") is None else float(r["lon"]),
                source_reliability=float(r.get("source_reliability") or 0.8),
                freshness_score=float(r.get("freshness_score") or 0.7),
            ))
        return cards, f"{table} via Databricks SQL"
    except Exception as exc:
        return [], f"Databricks SQL unavailable: {exc}"


def render_pick_html(pick: RankedPick) -> str:
    card = pick.card
    card_type = str(card.card_type or "local_update")
    category = str(card.category or "local")
    title = escape(str(card.title or "Local pick"))
    description = escape(str(card.description or "Source-backed local open-data card."))
    source_name = escape(str(card.source_name or "Databricks Gold table"))
    source_url = escape(normalized_url(str(card.source_url or "")))
    meta = escape(f"{source_name} · {distance_label(pick.distance_m)}")
    icon = source_icon(card_type, category)
    why = escape(pick.why_shown)
    return (
        f'<div class="pick"><b>{icon} {title}</b><br>'
        f'<span class="muted">{meta}</span><br>{description}<br>'
        f'<span class="muted">{why}</span><br>'
        f'<a class="visit" href="{source_url}" target="_blank" rel="noopener noreferrer">Visit Website</a></div>'
    )


params = st.query_params
page = params.get("page", "today")
if page not in {"today", "business", "about"}:
    page = "today"

location_source = params.get("source", st.session_state.get("location_source", "default"))
coords = params.get("coords", st.session_state.get("coords", DEFAULT_COORDS))
parsed = parse_coords(coords) or parse_coords(DEFAULT_COORDS)
lat, lon = parsed or (1.3521, 103.8198)
location = params.get("location", st.session_state.get("location", DEFAULT_LOCATION))
radius_m = DEFAULT_RADIUS_M if location_source != "browser" else 1500
interests = ["food", "grocery", "event", "deal"]
interests_value = ",".join(interests)

if get_geolocation and location_source != "browser":
    geo = get_geolocation(component_key=GEOLOCATION_KEY)
    st.session_state["geolocation_raw_debug"] = repr(geo)
    detected_coords = extract_geolocation_coords(geo)
    if detected_coords:
        apply_detected_location(
            detected_lat=detected_coords[0],
            detected_lon=detected_coords[1],
            detected_source="browser",
            current_page=page,
        )
    geolocation_error = extract_geolocation_error(geo)
    if geolocation_error:
        st.session_state["geolocation_error"] = geolocation_error
        if streamlit_js_eval:
            ip_geo = streamlit_js_eval(
                js_expressions="fetch('https://ipapi.co/json/').then(r => r.json())",
                key=IP_LOCATION_KEY,
            )
            st.session_state["ip_location_raw_debug"] = repr(ip_geo)
            ip_coords = extract_ip_location_coords(ip_geo)
            if ip_coords:
                apply_detected_location(
                    detected_lat=ip_coords[0],
                    detected_lon=ip_coords[1],
                    detected_source="browser",
                    current_page=page,
                )
elif get_geolocation is None:
    st.session_state["geolocation_raw_debug"] = "streamlit_js_eval.get_geolocation is unavailable"

st.session_state["geolocation_state_debug"] = {
    "page": page,
    "location": location,
    "coords": coords,
    "location_source": location_source,
    "is_browser_location": location_source == "browser",
    "error": st.session_state.get("geolocation_error"),
}

is_browser_location = location_source == "browser"
weather = fetch_weather(lat, lon)
weather_summary = f"{weather['temperature']} · {weather['forecast']}"

# Core dynamic recommendations querying and compilation
db_cards, databricks_source = load_nearby_databricks_picks(lat, lon)
physical_cards = list(db_cards) if db_cards else list(source_registry_cards())

# Append merchant-submitted promotions from Databricks SQL or local JSON fallback
business_cards = load_business_promotions(lat, lon, databricks_sql_settings())
physical_cards.extend(business_cards)

# Construct rich user context
context = UserContext(
    mode=params.get("mode", st.session_state.get("mode", "resident")),
    address=location,
    lat=lat,
    lon=lon,
    radius_m=radius_m,
    interests=tuple(interests),
    time_of_day=infer_time_of_day(),
    weather=weather["forecast"],
)

# Apply formal dynamic ranking engine on physical cards
ranked_physical_picks = rank_cards(physical_cards, context, limit=12)

# Extract and wrap Google Search anchor cards as low-ranked picks at the bottom of the feed
search_cards = area_anchor_cards(location, lat, lon)
ranked_search_picks = []
for card in search_cards:
    ranked_search_picks.append(
        RankedPick(
            card=card,
            score=0.1,  # Lower score so they logically sit below physical cards
            distance_m=0.0,
            why_shown=f"Shown because it is within 0m of your selected area."
        )
    )

# Combine for homepage feed visualization (physical first, search shortcuts at the bottom)
ranked_picks = ranked_physical_picks + ranked_search_picks
all_cards = physical_cards + search_cards

safe_location = escape(location)
safe_coords = escape(coords)
safe_first_interest = escape(interests[0])
safe_weather_summary = escape(weather_summary)
safe_weather_source = escape(weather["source"])
safe_location_source = "Browser location" if is_browser_location else "Default area"
safe_pick_scope = "near your selected area" if is_browser_location else "across Singapore"
safe_near_phrase = f"near {safe_location}" if is_browser_location else "across Singapore"
safe_databricks_source = escape(databricks_source)

filter_aliases = {
    "all": ("all",),
    "food": ("food", "hawker", "eat", "restaurant", "dining"),
    "grocery": ("grocery", "supermarket", "market", "store"),
    "event": ("event", "events", "community", "weekend"),
    "deal": ("deal", "deals", "promo", "promotion", "discount", "offer"),
}


def build_picks_feed(active_filters: list[str], max_distance_km: float) -> tuple[str, str]:
    selected_filters = [value for value in active_filters if value in filter_aliases and value != "all"]
    active_terms = tuple(term for value in selected_filters for term in filter_aliases[value])
    max_distance_m = max_distance_km * 1000
    scoped_picks = [
        pick for pick in ranked_picks
        if pick.distance_m is None or pick.distance_m <= max_distance_m
    ]
    if selected_filters:
        matched_picks = []
        for pick in scoped_picks:
            card = pick.card
            haystack = " ".join([
                card.card_type,
                card.category,
                card.title,
                card.description,
                " ".join(card.tags)
            ]).lower()
            if any(term in haystack for term in active_terms):
                matched_picks.append(pick)
        scoped_picks = matched_picks

    if scoped_picks:
        footer = f"{len(scoped_picks)} of {len(all_cards)} picks within {max_distance_km:g} km⌄"
        return "".join(render_pick_html(row) for row in scoped_picks), footer

    if ranked_picks:
        empty_html = (
            '<div class="pick" style="text-align: center; padding: 30px 20px;">'
            '<b>🔍 No matching picks found</b><br>'
            '<span class="muted" style="font-size: 0.9rem;">No active cards match this distance and keyword filter.</span><br>'
            '<span class="muted" style="font-size: 0.85rem; display: block; margin-top: 10px;">Try increasing distance or choosing another keyword.</span>'
            '</div>'
        )
        return empty_html, f"0 of {len(all_cards)} picks match filter⌄"

    fallback_html = (
        f'<div class="pick"><b>🤖 {safe_first_interest.title()} {safe_near_phrase}</b><br>'
        f'<span class="muted">{safe_databricks_source}</span><br>'
        'Databricks-backed picks are unavailable, so this placeholder is shown until SQL access is configured.<br>'
        '<span class="visit">Visit Website</span></div>'
        f'<div class="pick"><b>{weather["icon"]} Weather-aware plan</b><br>'
        f'<span class="muted">{safe_weather_summary}</span><br>'
        'Use this context to choose indoor, outdoor or transport-friendly options.<br>'
        '<span class="visit">Visit Website</span></div>'
        '<div class="pick"><b>🏷️ Singapore deal updates</b><br>'
        f'<span class="muted">Interests · {escape(", ".join(interests[:3]))}</span><br>'
        'Featured grocery offers and deal sources across Singapore.<br><span class="visit">Visit Website</span></div>'
    )
    return fallback_html, "Databricks SQL not ready⌄"


def make_url(target_page: str | None = None, **updates: str) -> str:
    data = {
        "page": target_page or page,
        "location": location,
        "coords": coords,
        "source": location_source,
    }
    data.update({k: v for k, v in updates.items() if v is not None})
    return "?" + urlencode(data)


def active(name: str) -> str:
    return "active" if page == name else ""


def render_tags(items: list[str]) -> str:
    return "".join(f'<span class="tag">{escape(item)} ×</span>' for item in items[:5])


# Try to load and base64-encode the logo
import base64

def get_logo_base64(filename: str = "logo.jpg") -> str:
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, "static", filename)
        if not os.path.exists(path):
            path = os.path.join("static", filename)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    return ""


logo_b64 = get_logo_base64("logo.jpg")
if logo_b64:
    logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" class="pin">'
else:
    logo_html = '<div class="pin-fallback"></div>'


st.markdown("""
<style>
:root {
    color-scheme: light !important;
    --bg: #F4F7FB;
    --text: #172B4D;
    --muted: #667085;
    --line: #E3EAF5;
    --blue: #0D6EFD;
    --green: #10B981;
    --app-h: calc(100dvh - 1.05rem);
    --chat-body-h: clamp(360px, calc(var(--app-h) - 250px), 900px);
    --chat-body-expanded-h: clamp(430px, calc(var(--app-h) - 215px), 980px);
    --picks-body-h: clamp(360px, calc(var(--app-h) - 145px), 1100px);
}
@supports not (height:100dvh) {
    :root {
        --app-h: calc(100vh - 1.05rem);
        --chat-body-h: clamp(360px, calc(var(--app-h) - 250px), 900px);
        --chat-body-expanded-h: clamp(430px, calc(var(--app-h) - 215px), 980px);
        --picks-body-h: clamp(360px, calc(var(--app-h) - 145px), 1100px);
    }
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="block-container"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    color-scheme: light !important;
    overflow: hidden !important;
}
[data-testid="stHeader"], section[data-testid="stSidebar"] {
    display: none !important;
}
[data-testid="stStatusWidget"] {
    visibility: hidden !important;
}
div.block-container, div[data-testid="stMainBlockContainer"], .main .block-container {
    max-width: none !important;
    padding: .65rem 1.45rem .45rem 1.15rem !important;
    height: 100dvh !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: .75rem !important;
    align-items: stretch !important;
    width: 100% !important;
    max-width: 100% !important;
}
div[data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
div[data-testid="column"] {
    min-width: 0 !important;
    overflow: visible !important;
}
div[data-testid="stMainBlockContainer"]:has(.business-page-marker),
div.block-container:has(.business-page-marker),
[data-testid="stAppViewContainer"]:has(.business-page-marker) {
    height: auto !important;
    min-height: 100dvh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
html:has(.business-page-marker),
body:has(.business-page-marker),
.stApp:has(.business-page-marker) {
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
.app-card {
    height: var(--app-h);
    width: calc(100% - 8px);
    margin-right: 8px;
    background: white;
    border: 1px solid var(--line);
    border-radius: 24px;
    box-shadow: 0 16px 38px rgba(23,43,77,.08);
    overflow: hidden;
    box-sizing: border-box;
}
.sidebar-card { padding: 26px 24px 18px 24px; }
.chat-card { padding: 28px 28px 18px 28px; }
.picks-card { padding: 28px 24px 18px 24px; }
.full-card { padding: 30px 32px 20px 32px; overflow-y: auto !important; }

.stMarkdown, .stCaption, label, p, span, div, h1, h2, h3, h4, h5, h6, li {
    color: var(--text) !important;
}
.muted, .stCaption, .stCaption * {
    color: var(--muted) !important;
}
h1 {
    font-size: clamp(1.65rem, 2.2vw, 2.05rem) !important;
    letter-spacing: .01em;
    margin: 0 0 .15rem 0 !important;
}
h2 {
    font-size: clamp(1.25rem, 1.55vw, 1.55rem) !important;
    margin: 0 0 .15rem 0 !important;
}
.brand {
    display: flex;
    gap: 13px;
    align-items: center;
    margin-bottom: clamp(14px, 2dvh, 20px);
}
.pin {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: white;
    border: 1px solid var(--line);
    box-shadow: 0 10px 22px rgba(13,110,253,.20);
    flex: 0 0 auto;
    object-fit: contain;
    padding: 2px;
    box-sizing: border-box;
}
.pin-fallback {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: linear-gradient(145deg, #0D6EFD, #20B2AA);
    box-shadow: 0 10px 22px rgba(13,110,253,.20);
    flex: 0 0 auto;
}
.brand-title {
    font-size: 21px;
    font-weight: 900;
    color: #0D2B5C;
}
.sg-red {
    color: #ED1B24 !important;
}
.subtitle {
    font-size: 12.5px;
    line-height: 1.45;
    color: var(--muted) !important;
    margin-top: 4px;
}
.nav {
    border-top: 1px solid var(--line);
    padding-top: 14px;
    margin-top: 8px;
}
.nav a {
    display: block;
    text-decoration: none !important;
    border-radius: 13px;
    padding: 10px 12px;
    font-size: 13.5px;
    font-weight: 800;
    margin-bottom: 5px;
    color: var(--text) !important;
}
.nav a.active {
    background: linear-gradient(90deg, #EAF2FF, #F6FAFF);
    color: #175CD3 !important;
    box-shadow: inset 3px 0 0 #0D6EFD;
}
.side-title {
    font-size: 20px;
    font-weight: 900;
    margin: clamp(13px, 2dvh, 18px) 0 5px 0;
}
.info-card {
    border: 1px solid #D8DFEA;
    border-radius: 18px;
    background: linear-gradient(180deg, #fff, #FBFCFE);
    padding: 12px 12px;
    margin: 10px 0;
    box-shadow: 0 5px 16px rgba(23,43,77,.045);
    width: 85%;
    margin-left: auto;
    margin-right: auto;
    box-sizing: border-box;
}
.info-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    margin: 8px 0;
}
.info-icon {
    width: 22px;
    text-align: center;
    flex: 0 0 auto;
}
.info-main {
    font-size: 12.6px;
    font-weight: 850;
    color: #172B4D !important;
    line-height: 1.35;
}
.info-sub {
    font-size: 11.2px;
    color: var(--muted) !important;
    line-height: 1.35;
}
.tag {
    border-radius: 999px;
    padding: 6px 10px;
    background: #EEF4FF;
    color: #175CD3 !important;
    font-size: 11.5px;
    font-weight: 800;
    display: inline-block;
    margin: 3px;
}
.tag-wrap {
    margin: 7px 0 12px 0;
}
.area-label {
    font-size: 11.8px;
    color: var(--muted) !important;
    font-weight: 750;
    margin: 8px 0 5px 2px;
}
.small-note {
    border: 1px solid #E8EEF8;
    border-radius: 13px;
    background: #F8FBFF;
    padding: 10px 12px;
    font-size: 11.5px;
    color: #4B5565 !important;
    line-height: 1.4;
}
.field {
    min-height: 44px;
    border: 1px solid #D8DFEA;
    border-radius: 13px;
    background: white;
    display: flex;
    align-items: center;
    padding: 0 13px;
    font-size: 12.5px;
    color: #4B5565 !important;
    margin-bottom: 9px;
    box-shadow: 0 2px 8px rgba(23,43,77,.025);
    box-sizing: border-box;
}
.status {
    display: inline-block;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 9px 14px;
    font-size: 12.5px;
    margin: 0 8px 12px 0;
    background: white;
    box-shadow: 0 2px 8px rgba(23,43,77,.025);
}
.bubble {
    border-radius: 18px;
    background: #F1F5F9;
    padding: 13px 16px;
    display: inline-block;
    margin: 12px;
    max-width: 68%;
    font-size: 14px;
    line-height: 1.45;
    box-shadow: 0 2px 8px rgba(23,43,77,.025);
}
.user {
    text-align: right;
}
.quick-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 14px;
}
.quick {
    border: 1px solid #D8DFEA;
    border-radius: 13px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12.5px;
    font-weight: 800;
    background: white;
    box-shadow: 0 2px 8px rgba(23,43,77,.025);
}
.inputbar {
    min-height: 58px;
    border: 1px solid #D8DFEA;
    border-radius: 18px;
    background: white;
    display: grid;
    grid-template-columns: 46px 1fr 58px;
    align-items: center;
    margin-top: 14px;
    box-shadow: 0 6px 18px rgba(23,43,77,.045);
}
.send {
    height: 44px;
    width: 44px;
    border-radius: 13px;
    background: var(--blue);
    color: white !important;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
}
.chatbox {
    height: var(--chat-body-h);
    border-radius: 18px;
    background: linear-gradient(180deg, #FFFFFF 0%, #FBFCFE 100%);
    border: 1px dashed #D8E2F0;
    padding: 18px;
    overflow-y: auto;
    box-sizing: border-box;
    margin-bottom: 12px;
}
.chatbox.expanded {
    height: var(--chat-body-expanded-h);
}
.thinking-line {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.thinking-spinner {
    width: 15px;
    height: 15px;
    border: 2px solid rgba(13,110,253,.16);
    border-top-color: var(--blue);
    border-radius: 50%;
    animation: spin 0.75s linear infinite;
}
.picklist {
    height: var(--picks-body-h);
    overflow-y: auto;
}
.pick {
    display: flow-root !important;
    min-height: clamp(112px, 17dvh, 135px);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 15px;
    background: white;
    margin-bottom: 13px;
    box-shadow: 0 5px 16px rgba(23,43,77,.045);
    width: calc(100% - 6px);
    box-sizing: border-box;
}
.pick b { font-size: 15px; }
.footer {
    text-align: center;
    color: var(--muted) !important;
    font-size: 11.5px;
    margin-top: 9px;
}
.visit {
    float: right !important;
    margin-top: 10px;
    border: 1px solid var(--line);
    border-radius: 11px;
    padding: 8px 11px;
    font-size: 11.5px;
    background: white;
    color: #0D2B5C !important;
    font-weight: 750;
}
.main-shell-title {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
}
.view-all {
    font-size: 13px;
    color: #175CD3 !important;
    font-weight: 800;
    margin-top: 6px;
}
.sidebar-note {
    font-size: 11.8px;
    color: var(--muted) !important;
    margin-top: 10px;
    line-height: 1.35;
}
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin: 18px 0;
}
.kpi {
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 14px;
    background: #fff;
    box-shadow: 0 5px 16px rgba(23,43,77,.045);
    overflow: hidden;
    position: relative;
    min-width: 0;
}
.kpi b { display: block; font-size: 1.35rem; margin-top: 4px; }
.kpi:nth-child(1){background:linear-gradient(145deg,#ECFDF3,#FFFFFF);border-color:#B7E4CA}.kpi:nth-child(1) b{color:#047857!important}
.kpi:nth-child(2){background:linear-gradient(145deg,#EFF6FF,#FFFFFF);border-color:#BFDBFE}.kpi:nth-child(2) b{color:#1D4ED8!important}
.kpi:nth-child(3){background:linear-gradient(145deg,#FFF7ED,#FFFFFF);border-color:#FED7AA}.kpi:nth-child(3) b{color:#C2410C!important}
.kpi:nth-child(4){background:linear-gradient(145deg,#F5F3FF,#FFFFFF);border-color:#DDD6FE}.kpi:nth-child(4) b{color:#6D28D9!important}
.form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 14px;
}
.form-field {
    border: 1px solid #D8DFEA;
    border-radius: 13px;
    padding: 12px;
    background: #fff;
    color: #4B5565 !important;
    font-size: 13px;
}
.wide { grid-column: 1/-1; }
.preview-card {
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 18px;
    background: #fff;
    box-shadow: 0 8px 22px rgba(23,43,77,.055);
    margin-top: 14px;
    width: calc(100% - 6px);
    box-sizing: border-box;
}
.about-section { margin-top: 22px; }
.about-section h2 { margin-bottom: 8px !important; }
.about-section ul { margin-top: 8px; line-height: 1.8; }
.demo-hero{background:linear-gradient(135deg,#EFF6FF 0%,#FFFFFF 55%,#ECFDF3 100%);border:1px solid #D8E7FF;border-radius:22px;padding:22px;margin-bottom:20px}
.demo-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}
.demo-card{border:1px solid var(--line);border-radius:18px;padding:16px;background:#fff;box-shadow:0 8px 20px rgba(23,43,77,.055)}
.demo-card b{font-size:1rem}.demo-card p{font-size:.9rem;line-height:1.55;color:#4B5565!important}
.tech-pill{display:inline-block;margin:5px 6px 0 0;padding:8px 11px;border-radius:999px;background:#EEF4FF;color:#175CD3!important;font-weight:850;font-size:.82rem}
.value-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:18px 0}
.value-item{border-radius:16px;padding:13px;background:#0D2B5C;color:#fff!important}.value-item b,.value-item span{color:#fff!important}.value-item span{font-size:.8rem;opacity:.82}

@media(max-height: 760px) {
    :root { --app-h: calc(100dvh - .9rem); }
    .pick { min-height: 108px; }
    .inputbar { min-height: 52px; }
    .quick { min-height: 39px; }
    .brand { margin-bottom: 12px; }
    .field { min-height: 38px; margin-bottom: 7px; }
    .nav a { padding: 8px 10px; }
    .tag { padding: 5px 8px; }
    .sidebar-note { display: none; }
    .info-card { padding: 10px 12px; }
    .small-note { display: none; }
}

/* Card styling uses marker classes so it works on older Streamlit builds without st.container(key=...). */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .sidebar-card-marker),
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker),
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .picks-card-marker),
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker),
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .preview-card-marker) {
    background: white !important;
    border: 1px solid var(--line) !important;
    border-radius: 24px !important;
    box-shadow: 0 16px 38px rgba(23,43,77,.08) !important;
    height: var(--app-h) !important;
    width: calc(100% - 8px) !important;
    max-width: calc(100% - 8px) !important;
    margin-right: 8px !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    position: relative !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .sidebar-card-marker) {
    padding: 24px 16px 18px 16px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .sidebar-card-marker)::-webkit-scrollbar {
    width: 0px !important;
    background: transparent !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) {
    padding: 24px 26px 14px 26px !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .picks-card-marker) {
    padding: 24px 18px 14px 18px !important;
    overflow-x: hidden !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) {
    padding: 26px 24px 16px 28px !important;
    height: auto !important;
    min-height: var(--app-h) !important;
    max-height: none !important;
    overflow-y: visible !important;
    overflow-x: hidden !important;
    padding-bottom: 54px !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .preview-card-marker) {
    padding: 26px 14px 16px 18px !important;
    overflow-x: hidden !important;
}

div[data-testid="stMainBlockContainer"]:has(.business-page-marker) div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .preview-card-marker) {
    height: auto !important;
    min-height: var(--app-h) !important;
    max-height: none !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker)::-webkit-scrollbar {
    width: 8px !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker)::-webkit-scrollbar-thumb {
    background: #CBD5E1 !important;
    border-radius: 999px !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker)::-webkit-scrollbar-track {
    background: transparent !important;
}

/* Custom Overrides to Strip Streamlit Native Border and Spacing on Forms */
div[data-testid="stForm"] {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}

/* Style premium inputs */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
    border: 1px solid #D8DFEA !important;
    border-radius: 13px !important;
    min-height: 44px !important;
    background-color: white !important;
    color: var(--text) !important;
    font-size: 13.5px !important;
    padding: 0 16px !important;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.05) !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"],
div[data-testid="stMultiSelect"] [data-baseweb="select"],
div[data-testid="stDateInput"] input {
    width: 100% !important;
    box-sizing: border-box !important;
}
div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px rgba(13,110,253,0.15) !important;
    outline: none !important;
}

div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #EAF2FF !important;
    border: 1px solid #B8D4FF !important;
    color: #0B3B7A !important;
    border-radius: 999px !important;
    font-weight: 800 !important;
}
div[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
div[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
    color: #0B3B7A !important;
    fill: #0B3B7A !important;
}

/* Style auxiliary buttons inside chat container */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stButton"] button {
    border: 1px solid #D8DFEA !important;
    border-radius: 13px !important;
    min-height: 44px !important;
    font-size: 12.5px !important;
    font-weight: 800 !important;
    background: white !important;
    color: var(--text) !important;
    box-shadow: 0 2px 8px rgba(23,43,77,.025) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stButton"] button:hover {
    border-color: var(--blue) !important;
    color: var(--blue) !important;
    background: #F5F9FF !important;
}

/* Style the submit button inside chat container */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
    background: var(--blue) !important;
    color: white !important;
    border: none !important;
    border-radius: 14px !important;
    font-size: 16px !important;
    font-weight: 900 !important;
    box-shadow: 0 8px 18px rgba(13,110,253,.22) !important;
    min-height: 58px !important;
    height: 58px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
    background: #1b5ed7 !important;
    color: white !important;
    box-shadow: 0 8px 22px rgba(13,110,253,.32) !important;
}

/* Style premium input inside chat form and keep the send button aligned. */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stForm"] div[data-testid="stTextInput"] input {
    min-height: 58px !important;
    height: 58px !important;
    line-height: 58px !important;
    border-radius: 16px !important;
    font-size: 14px !important;
    padding: 0 18px !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 8px !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker) div[data-testid="stForm"] div[data-testid="element-container"] {
    margin: 0 !important;
    padding: 0 !important;
}

/* Style the submit button in the business form container */
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #0D6EFD 0%, #2563EB 100%) !important;
    color: white !important;
    justify-content: center !important;
    font-weight: 900 !important;
    border: 0 !important;
    border-radius: 999px !important;
    box-shadow: 0 14px 26px rgba(13, 110, 253, 0.24) !important;
    min-height: 48px !important;
    width: auto !important;
    min-width: 210px !important;
    padding: 0 28px !important;
    letter-spacing: .01em !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button *,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stButton"] button * {
    color: white !important;
    opacity: 1 !important;
}
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker) div[data-testid="stForm"] div[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, #0B5ED7 0%, #1D4ED8 100%) !important;
    color: white !important;
    box-shadow: 0 16px 30px rgba(13, 110, 253, 0.30) !important;
}

/* Strip borders and backgrounds from filter button containers */
div[class*="st-key-filter_btn_"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    height: auto !important;
}

/* Style filter pill buttons inside picks card container (inactive state) */
div[class*="st-key-filter_btn_"] button {
    border: none !important;
    border-radius: 999px !important;
    min-height: 32px !important;
    height: 32px !important;
    padding: 0px 10px !important;
    font-size: 11.5px !important;
    font-weight: 800 !important;
    background-color: #EEF4FF !important;
    color: #175CD3 !important;
    box-shadow: none !important;
    transition: all 0.2s ease !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-direction: row;
    gap: 4px !important;
    white-space: nowrap !important;
    width: 100% !important;
}
div[class*="st-key-filter_btn_"] button:hover {
    background-color: #E0ECFF !important;
    color: #114B9E !important;
}

/* Style filter pill buttons inside picks card container (active state) */
div[class*="st-key-filter_btn_"] button[kind="primary"] {
    background: var(--blue) !important;
    color: white !important;
}
div[class*="st-key-filter_btn_"] button[kind="primary"]:hover {
    background: #1b5ed7 !important;
    color: white !important;
}

/* Force filter button text properties to stay compact */
div[class*="st-key-filter_btn_"] button * {
    white-space: nowrap !important;
    word-break: keep-all !important;
    font-size: 11.5px !important;
    line-height: 1 !important;
}

[data-stale="true"],
div[data-testid="stVerticalBlock"][data-stale="true"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .sidebar-card-marker)[data-stale="true"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker)[data-stale="true"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .picks-card-marker)[data-stale="true"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker)[data-stale="true"],
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .preview-card-marker)[data-stale="true"],
[data-testid="stForm"][data-stale="true"],
[data-testid="stMarkdownContainer"][data-stale="true"] {
    opacity: 1 !important;
    background: white !important;
    border-color: var(--line) !important;
    transition: none !important;
}

div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .sidebar-card-marker):has([data-stale="true"]) > div,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .chat-card-marker):has([data-stale="true"]) > div,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .picks-card-marker):has([data-stale="true"]) > div,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .business-form-marker):has([data-stale="true"]) > div,
div[data-testid="stVerticalBlock"]:has(> div[data-testid="element-container"] .preview-card-marker):has([data-stale="true"]) > div {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Custom animated bouncing typing indicator */
@keyframes typing-bounce {
    0%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-6px); }
}
.typing-dot {
    width: 6px;
    height: 6px;
    background-color: var(--muted) !important;
    border-radius: 50%;
    display: inline-block;
    animation: typing-bounce 1.4s infinite ease-in-out both;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
</style>
""", unsafe_allow_html=True)


def render_sidebar():
    with st.container():
        st.markdown('<div class="sidebar-card-marker"></div>', unsafe_allow_html=True)
        st.markdown(f'''
<div class="brand">{logo_html}<div><div class="brand-title">GoAround <span class="sg-red">SG</span></div><div class="subtitle">AI local discovery assistant<br>for useful lobang near you.</div></div></div>
<div class="nav"><a class="{active('today')}" href="{make_url('today')}" target="_self">● GoAround Today</a><a class="{active('business')}" href="{make_url('business')}" target="_self">○ Business Promotion</a><a class="{active('about')}" href="{make_url('about')}" target="_self">○ What is GoAround?</a></div>
<div class="side-title">My area</div><div class="subtitle">Auto-detected when browser permission is allowed.</div>
<div class="info-card">
  <div class="info-row"><div class="info-icon">📍</div><div><div class="info-main">{safe_location}</div><div class="info-sub">{safe_location_source}</div></div></div>
  <div class="info-row"><div class="info-icon">{weather['icon']}</div><div><div class="info-main">{safe_weather_summary}</div><div class="info-sub">{safe_weather_source}</div></div></div>
  <div class="info-row"><div class="info-icon">🧭</div><div><div class="info-main">{safe_coords}</div><div class="info-sub">Approx. centre point</div></div></div>
</div>
<div class="footer" style="margin-top:15px; text-align:left; font-size:11px; line-height:1.4;">©2026 GoAroundSG.<br>Terms of Service. Privacy Policy</div>
''', unsafe_allow_html=True)


if page == "today":
    sidebar_col, chat_col, picks_col = st.columns([0.21, 0.53, 0.26], gap="medium")
    with sidebar_col:
        render_sidebar()

    with chat_col:
        with st.container():
            st.markdown('<div class="chat-card-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'''
<h1>Ask GoAround</h1><div class="muted">Your conversation-style local assistant.</div>
<div style="margin-top:12px; margin-bottom:12px;"><span class="status">{weather['icon']} {safe_weather_summary}</span><span class="status">📍 {safe_location}</span></div>
''', unsafe_allow_html=True)

            # Conversational state tracking
            if "ask_messages" not in st.session_state:
                st.session_state["ask_messages"] = []
            st.session_state.pop("pending_query", None)
            
            def render_chat_history(include_thinking: bool = False) -> None:
                chat_history_html = ""
                conversation_messages = st.session_state["ask_messages"]
                chatbox_class = "chatbox expanded" if conversation_messages else "chatbox"
                if not conversation_messages:
                    chat_history_html += f'''
<div style="margin: 10px 0;">
  🤖 <span class="bubble">
    Hello! I'm <b>Ask GoAround</b>, your hyperlocal discovery assistant. 😊<br><br>
    Since you're near <b>{safe_location}</b>, I can help you find things like:<br>
    🍲 <b>Local Food & Coffee</b>: Hidden gems or cheap eats nearby.<br>
    🏷️ <b>Lobang & Deals</b>: Supermarket discounts and retail promotions.<br>
    🎪 <b>Things To Do</b>: Parks, events, and family activities.<br>
    ☔ <b>Weather-Aware Ideas</b>: Great indoor plans if it's rainy outside.<br><br>
    What are you in the mood for today?
  </span>
</div>
'''
                for msg in conversation_messages[-8:]:
                    role = msg["role"]
                    content = escape(msg["content"]).replace("\n", "<br>")
                    if role == "user":
                        chat_history_html += f'<div style="text-align:right; margin: 10px 0;"><span class="bubble" style="background:#EAF2FF; text-align:left;">{content}</span> 👤</div>'
                    else:
                        chat_history_html += f'<div style="margin: 10px 0;">🤖 <span class="bubble">{content}</span></div>'
                if include_thinking:
                    chat_history_html += f'''
<div style="margin: 10px 0;">
  🤖 <span class="bubble thinking-line" style="padding: 12px 16px;">
    <span class="thinking-spinner"></span>
    <span>Thinking through nearby options</span>
    <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
  </span>
</div>
'''
                chat_history_html += '<div id="chat-bottom"></div>'
                chat_placeholder.markdown(f'''
<div class="{chatbox_class}">
{chat_history_html}
</div>
''', unsafe_allow_html=True)
            
            chat_placeholder = st.empty()

            # Real input form with native text input that styles beautifully
            with st.form("ask_form", clear_on_submit=True):
                ic, sc = st.columns([9, 1])
                q_input = ic.text_input("Ask", placeholder="Ask GoAround about this area or another place...", label_visibility="collapsed")
                submitted = sc.form_submit_button("➤", use_container_width=True)
                
            st.markdown(f'''
<div class="footer" style="margin-top:10px;">Go Around can make mistakes. Please check details at the source</div>
''', unsafe_allow_html=True)

            user_query = q_input.strip() if submitted and q_input.strip() else None
            if user_query:
                st.session_state["ask_messages"].append({"role": "user", "content": user_query})
                render_chat_history(include_thinking=True)
                ans = answer_with_databricks(
                    question=user_query,
                    context=context,
                    ranked=ranked_physical_picks,
                    fallback="I am looking up details...",
                )
                st.session_state["ask_messages"].append({"role": "assistant", "content": ans})
                render_chat_history()
                if streamlit_js_eval:
                    streamlit_js_eval(
                        js_expressions=(
                            "setTimeout(() => {"
                            "const boxes = window.parent.document.querySelectorAll('.chatbox');"
                            "const box = boxes[boxes.length - 1];"
                            "if (box) { box.scrollTop = box.scrollHeight; }"
                            "}, 100); 'ok';"
                        ),
                        key=f"chat_scroll_{len(st.session_state['ask_messages'])}",
                    )
            else:
                render_chat_history()

    with picks_col:
        with st.container():
            st.markdown('<div class="picks-card-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'''
<div class="main-shell-title" style="margin-top: 14px; margin-bottom: 12px;">
  <div>
    <h2>Today’s Picks</h2>
    <div class="muted">Curated source-backed picks {safe_pick_scope}.</div>
  </div>
</div>
''', unsafe_allow_html=True)
            distance_filter_km = st.slider(
                "Distance radius",
                min_value=0.0,
                max_value=3.0,
                value=float(st.session_state.get("distance_filter_km", min(radius_m / 1000, 3.0))),
                step=0.1,
                format="%.1f km",
                key="distance_filter_km",
            )
            filter_labels = {
                "food": "🍴 Food, hawker, dining",
                "grocery": "🛒 Grocery, supermarket, market",
                "event": "📅 Events, community, weekend",
                "deal": "🏷️ Deals, promos, offers",
            }
            active_filters = st.multiselect(
                "Filter criteria",
                options=list(filter_labels.keys()),
                format_func=lambda value: filter_labels[value],
                default=st.session_state.get("active_filters", []),
                key="active_filters",
            )
            picks_html, picks_footer = build_picks_feed(active_filters, distance_filter_km)
            safe_picks_footer = escape(picks_footer)

            st.markdown(f'''
<div class="picklist" style="margin-top: 14px;">{picks_html}</div>
<div class="footer" style="color:#175CD3!important;font-weight:800; margin-top: 10px;">{safe_picks_footer}</div>
''', unsafe_allow_html=True)

elif page == "business":
    st.markdown('<div class="business-page-marker"></div>', unsafe_allow_html=True)
    sidebar_col, form_col, preview_col = st.columns([0.21, 0.53, 0.26], gap="medium")
    with sidebar_col:
        render_sidebar()
    with form_col:
        with st.container():
            st.markdown('<div class="business-form-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'''
<h1>Business Promotion</h1><div class="muted">Create a local promotion that can appear in Today’s Picks for {safe_location}.</div>
<div class="kpi-grid"><div class="kpi"><span class="muted">Active</span><b>3</b></div><div class="kpi"><span class="muted">Clicks</span><b>128</b></div><div class="kpi"><span class="muted">Saves</span><b>47</b></div><div class="kpi"><span class="muted">Views</span><b>612</b></div></div>
<h2>Create Promotion</h2>
''', unsafe_allow_html=True)
            
            # Interactive Streamlit form
            with st.form("business_form"):
                col1, col2 = st.columns(2)
                b_name = col1.text_input("Business name", value="Ah Boyz Chicken Rice")
                p_title = col2.text_input("Promotion title *", value="50% Off Signature Chicken Rice (Dinner Special)")
                
                col3, col4 = st.columns(2)
                p_category = col3.selectbox("Category *", ["Food & Dining", "Grocery", "Mall", "Family", "Fitness"])
                p_area = col4.text_input("Location / Area *", value=location)
                
                col5, col6 = st.columns(2)
                p_from = col5.date_input("Valid from")
                p_to = col6.date_input("Valid to")
                
                p_interests = st.multiselect("Audience / Interests", ["food", "grocery", "event", "deal", "fitness", "tourist"], default=["food", "deal"])
                
                p_description = st.text_area("Short description *", value="Enjoy our signature Hainanese Chicken Rice at 50% off for dinner! Freshly steamed chicken, fragrant rice, and our homemade chilli.")
                p_url = st.text_input("CTA link (source url) *", value="https://example.com/AhBoyzDinnerDeal")
                
                publish_btn = st.form_submit_button("Publish Promotion", use_container_width=False)
                
            st.markdown(f'''
<div class="footer" style="margin-top:10px;">Submitted promotions appear immediately in Today's Picks on the homepage.</div>
''', unsafe_allow_html=True)
        
        if publish_btn:
            if not p_url.startswith("http"):
                st.error("Please provide a valid source URL starting with http:// or https:// to verify this deal.")
            else:
                new_promo = create_business_promo_card(
                    business_name=b_name,
                    title=p_title,
                    description=p_description,
                    category=p_category,
                    source_url=p_url,
                    lat=lat,
                    lon=lon,
                    location_name=p_area,
                    valid_until=p_to.isoformat(),
                    tags=p_interests,
                )
                saved = save_business_promotion(new_promo, databricks_sql_settings())
                if saved:
                    st.success("🎉 Promotion published to Databricks SQL successfully! Check the 'GoAround Today' tab to see it ranked near you.")
                else:
                    st.warning("⚠️ Saved promotion locally as backup. Check the 'GoAround Today' tab to see it ranked near you.")
                st.rerun()
                
    with preview_col:
        with st.container():
            st.markdown('<div class="preview-card-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'''
<h2>Preview</h2><div class="muted">How your promotion appears to users in real-time.</div>
<div class="preview-card" style="margin-top:20px;">
<div class="tag" style="background:#FFE6E2; color:#D32F2F !important;">{escape(p_category.upper())}</div>
<h2 style="margin-top:16px!important; font-size: 1.25rem;">{escape(p_title)}</h2>
<div class="muted" style="font-size:0.9rem; margin-top:8px;">{escape(p_description)}</div>
<br>
<div style="font-size:0.85rem; color:var(--muted);"><span class="info-icon">📍</span> {escape(p_area)}</div>
<div style="font-size:0.85rem; color:var(--muted); margin-top:4px;"><span class="info-icon">🏢</span> {escape(b_name)}</div>
<br>
<a class="visit" href="{escape(p_url)}" target="_blank">View details ↗</a>
</div>
''', unsafe_allow_html=True)

else:  # about page
    sidebar_col, content_col = st.columns([0.21, 0.79], gap="medium")
    with sidebar_col:
        render_sidebar()
    with content_col:
        st.markdown(f'''
<div class="app-card full-card">
  <div class="demo-hero">
    <h1>GoAround SG: source-backed hyperlocal discovery</h1>
    <div class="muted">A Databricks-powered assistant that helps residents, visitors, and local businesses discover useful things nearby. Demo area: {safe_location}.</div>
  </div>
  <div class="value-strip">
    <div class="value-item"><b>Less searching</b><br><span>One local answer instead of many tabs.</span></div>
    <div class="value-item"><b>More trust</b><br><span>Cards link back to public or business sources.</span></div>
    <div class="value-item"><b>Context aware</b><br><span>Location, weather, distance, and interests matter.</span></div>
    <div class="value-item"><b>Local growth</b><br><span>Nearby businesses can publish relevant promotions.</span></div>
  </div>
  <div class="demo-grid">
    <div class="demo-card"><b>Problem</b><p>Singapore has many open datasets and local sources, but they are fragmented. Users must know what to search for, compare sources, and still decide what is useful nearby right now.</p></div>
    <div class="demo-card"><b>Solution</b><p>GoAround turns open data, source registries, weather, distance, and business promotions into ranked daily picks plus a conversational assistant.</p></div>
    <div class="demo-card"><b>Demo flow</b><p>Open Today, allow location, adjust distance and criteria, ask Ask GoAround, then publish a mock promotion from the Business page to see how merchants can join the feed.</p></div>
  </div>
  <div class="about-section"><h2>Who benefits?</h2><p><b>Residents</b> find food, parks, family activities, and deals without manually checking many apps. <b>Visitors</b> get a short local plan around where they are. <b>Businesses</b> can surface timely promotions to nearby users instead of relying only on broad social ads.</p></div>
  <div class="about-section"><h2>Databricks technology used</h2><span class="tech-pill">Databricks Apps hosting</span><span class="tech-pill">Delta Lake / Lakehouse tables</span><span class="tech-pill">Databricks SQL warehouse</span><span class="tech-pill">Model Serving / GenAI-ready assistant</span><span class="tech-pill">Bronze-Silver-Gold data pipeline</span><p class="muted" style="margin-top:12px;">Candidate cards can be prepared as Gold tables, queried through Databricks SQL, ranked by context, and explained through an AI assistant with source-backed guardrails.</p></div>
  <div class="about-section"><h2>Why it is valuable</h2><p>GoAround demonstrates how public data and merchant-submitted data can become a practical daily local companion. The product value is not just a chatbot: it is a trusted hyperlocal retrieval, ranking, and promotion layer that can scale across Singapore neighbourhoods.</p></div>
  <div class="footer">GoAround SG — Team R4131N. Source-backed local discovery. Verify final details at source.</div>
</div>
''', unsafe_allow_html=True)
