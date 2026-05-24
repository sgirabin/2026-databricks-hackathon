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
radius_label = f"{radius_m / 1000:g} km" if is_browser_location else "Singapore-wide"
discovery_subtitle = "Discovery radius" if is_browser_location else "Discovery scope"
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
safe_radius_label = escape(radius_label)
safe_first_interest = escape(interests[0])
safe_weather_summary = escape(weather_summary)
safe_weather_source = escape(weather["source"])
safe_location_source = "Browser location" if is_browser_location else "Default area"
safe_pick_scope = f"within {safe_radius_label}" if is_browser_location else "across Singapore"
safe_near_phrase = f"near {safe_location}" if is_browser_location else "across Singapore"
safe_databricks_source = escape(databricks_source)

# Compile the picks feed HTML, applying the active filter if selected
active_filter = st.session_state.get("active_filter", "all")
filter_aliases = {
    "all": ("all",),
    "food": ("food", "hawker", "eat", "restaurant", "dining"),
    "grocery": ("grocery", "supermarket", "market", "store"),
    "event": ("event", "events", "community", "weekend"),
    "deal": ("deal", "deals", "promo", "promotion", "discount", "offer"),
}
if active_filter not in filter_aliases:
    active_filter = "all"
    st.session_state["active_filter"] = "all"
if active_filter != "all":
    active_terms = filter_aliases[active_filter]
    filtered_picks = []
    for pick in ranked_picks:
        card = pick.card
        # Check if active filter matches card type, category, title, description, or tags
        haystack = " ".join([
            card.card_type,
            card.category,
            card.title,
            card.description,
            " ".join(card.tags)
        ]).lower()
        if any(term in haystack for term in active_terms):
            filtered_picks.append(pick)
            
    if filtered_picks:
        picks_html = "".join(render_pick_html(row) for row in filtered_picks)
        picks_footer = f"{len(filtered_picks)} of {len(all_cards)} picks match filter⌄"
    else:
        picks_html = (
            '<div class="pick" style="text-align: center; padding: 30px 20px;">'
            '<b>🔍 No matching picks found</b><br>'
            '<span class="muted" style="font-size: 0.9rem;">There are no active cards near you matching this filter.</span><br>'
            '<span class="muted" style="font-size: 0.85rem; display: block; margin-top: 10px;">Try switching to another category above.</span>'
            '</div>'
        )
        picks_footer = f"0 of {len(all_cards)} picks match filter⌄"
else:
    if ranked_picks:
        picks_html = "".join(render_pick_html(row) for row in ranked_picks)
        picks_footer = f"{len(all_cards)} candidates ranked via Databricks⌄"
    else:
        picks_html = (
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
        picks_footer = "Databricks SQL not ready⌄"

safe_picks_footer = escape(picks_footer)


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
    --chat-body-h: clamp(190px, calc(var(--app-h) - 390px), 680px);
    --picks-body-h: clamp(360px, calc(var(--app-h) - 145px), 1100px);
}
@supports not (height:100dvh) {
    :root {
        --app-h: calc(100vh - 1.05rem);
        --chat-body-h: clamp(190px, calc(var(--app-h) - 390px), 680px);
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
    padding: .55rem .75rem .35rem .75rem !important;
    height: 100dvh !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}
div[data-testid="stHorizontalBlock"] {
    gap: 1rem !important;
    align-items: stretch !important;
}
div[data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
.app-card {
    height: var(--app-h);
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
    padding: 13px 14px;
    margin: 10px 0;
    box-shadow: 0 5px 16px rgba(23,43,77,.045);
}
.info-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin: 8px 0;
}
.info-icon {
    width: 22px;
    text-align: center;
    flex: 0 0 auto;
}
.info-main {
    font-size: 13px;
    font-weight: 850;
    color: #172B4D !important;
    line-height: 1.35;
}
.info-sub {
    font-size: 11.5px;
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
    gap: 12px;
    margin: 18px 0;
}
.kpi {
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 14px;
    background: #fff;
    box-shadow: 0 5px 16px rgba(23,43,77,.045);
}
.kpi b { display: block; font-size: 1.35rem; margin-top: 4px; }
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
}
.about-section { margin-top: 22px; }
.about-section h2 { margin-bottom: 8px !important; }
.about-section ul { margin-top: 8px; line-height: 1.8; }

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

/* Precise stVerticalBlockBorder Container Card Styles */
div[data-testid="stVerticalBlockBorder-sidebar_card_container"],
div[data-testid="stVerticalBlockBorder-chat_card_container"],
div[data-testid="stVerticalBlockBorder-picks_card_container"],
div[data-testid="stVerticalBlockBorder-business_form_container"],
div[data-testid="stVerticalBlockBorder-preview_card_container"] {
    background: white !important;
    border: 1px solid var(--line) !important;
    border-radius: 24px !important;
    box-shadow: 0 16px 38px rgba(23,43,77,.08) !important;
    height: var(--app-h) !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
    position: relative !important;
}

div[data-testid="stVerticalBlockBorder-sidebar_card_container"] {
    padding: 26px 24px 18px 24px !important;
    overflow-y: auto !important;
}
div[data-testid="stVerticalBlockBorder-sidebar_card_container"]::-webkit-scrollbar {
    width: 0px !important;
    background: transparent !important;
}

div[data-testid="stVerticalBlockBorder-chat_card_container"] {
    padding: 24px 26px 14px 26px !important;
}

div[data-testid="stVerticalBlockBorder-picks_card_container"] {
    padding: 24px 20px 14px 20px !important;
}

div[data-testid="stVerticalBlockBorder-business_form_container"] {
    padding: 26px 28px 16px 28px !important;
    height: var(--app-h) !important;
    max-height: var(--app-h) !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding-bottom: 42px !important;
    overscroll-behavior: contain !important;
}

div[data-testid="stVerticalBlockBorder-preview_card_container"] {
    padding: 26px 20px 16px 20px !important;
}

div[data-testid="stVerticalBlockBorder-business_form_container"]::-webkit-scrollbar {
    width: 8px !important;
}
div[data-testid="stVerticalBlockBorder-business_form_container"]::-webkit-scrollbar-thumb {
    background: #CBD5E1 !important;
    border-radius: 999px !important;
}
div[data-testid="stVerticalBlockBorder-business_form_container"]::-webkit-scrollbar-track {
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
}
div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--blue) !important;
    box-shadow: 0 0 0 3px rgba(13,110,253,0.15) !important;
    outline: none !important;
}

/* Style quick action buttons inside chat container */
div[data-testid="stVerticalBlockBorder-chat_card_container"] div[data-testid="stButton"] button {
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
div[data-testid="stVerticalBlockBorder-chat_card_container"] div[data-testid="stButton"] button:hover {
    border-color: var(--blue) !important;
    color: var(--blue) !important;
    background: #F5F9FF !important;
}

/* Style the submit button inside chat container */
div[data-testid="stVerticalBlockBorder-chat_card_container"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
    background: var(--blue) !important;
    color: white !important;
    border: none !important;
    border-radius: 14px !important;
    font-size: 16px !important;
    font-weight: 900 !important;
    box-shadow: 0 8px 18px rgba(13,110,253,.22) !important;
    min-height: 48px !important;
    height: 48px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
div[data-testid="stVerticalBlockBorder-chat_card_container"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
    background: #1b5ed7 !important;
    color: white !important;
    box-shadow: 0 8px 22px rgba(13,110,253,.32) !important;
}

/* Style premium input inside chat form specifically to be taller and easier to tap. */
div[data-testid="stVerticalBlockBorder-chat_card_container"] div[data-testid="stForm"] div[data-testid="stTextInput"] input {
    min-height: 58px !important;
    height: 58px !important;
    border-radius: 16px !important;
    font-size: 14px !important;
    padding: 0 18px !important;
}

/* Style the submit button in the business form container */
div[data-testid="stVerticalBlockBorder-business_form_container"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button,
div[data-testid="stVerticalBlockBorder-business_form_container"] div[data-testid="stForm"] div[data-testid="stButton"] button {
    background: linear-gradient(90deg, #0D6EFD, #2563EB) !important;
    color: white !important;
    justify-content: center !important;
    font-weight: 900 !important;
    border: 0 !important;
    border-radius: 13px !important;
    box-shadow: 0 8px 18px rgba(13, 110, 253, 0.22) !important;
    min-height: 44px !important;
}
div[data-testid="stVerticalBlockBorder-business_form_container"] div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover,
div[data-testid="stVerticalBlockBorder-business_form_container"] div[data-testid="stForm"] div[data-testid="stButton"] button:hover {
    background: linear-gradient(90deg, #0B5ED7, #1D4ED8) !important;
    color: white !important;
    box-shadow: 0 8px 22px rgba(13, 110, 253, 0.32) !important;
}

/* Strip borders and backgrounds from filter button containers */
div[data-testid*="stVerticalBlockBorder-filter_btn_"] {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    height: auto !important;
}

/* Style filter pill buttons inside picks card container (inactive state) */
div[data-testid*="stVerticalBlockBorder-filter_btn_"] button {
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
div[data-testid*="stVerticalBlockBorder-filter_btn_"] button:hover {
    background-color: #E0ECFF !important;
    color: #114B9E !important;
}

/* Style filter pill buttons inside picks card container (active state) */
div[data-testid*="stVerticalBlockBorder-filter_btn_"] button[kind="primary"] {
    background: var(--blue) !important;
    color: white !important;
}
div[data-testid*="stVerticalBlockBorder-filter_btn_"] button[kind="primary"]:hover {
    background: #1b5ed7 !important;
    color: white !important;
}

/* Force filter button text properties to stay compact */
div[data-testid*="stVerticalBlockBorder-filter_btn_"] button * {
    white-space: nowrap !important;
    word-break: keep-all !important;
    font-size: 11.5px !important;
    line-height: 1 !important;
}

[data-stale="true"],
div[data-testid="stVerticalBlock"][data-stale="true"],
div[data-testid*="stVerticalBlockBorder-"][data-stale="true"],
[data-testid="stForm"][data-stale="true"],
[data-testid="stMarkdownContainer"][data-stale="true"] {
    opacity: 1 !important;
    background: white !important;
    border-color: var(--line) !important;
    transition: none !important;
}

div[data-testid*="stVerticalBlockBorder-"]:has([data-stale="true"]) > div {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
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
    with st.container(key="sidebar_card_container"):
        st.markdown('<div class="sidebar-card-marker"></div>', unsafe_allow_html=True)
        st.markdown(f'''
<div class="brand">{logo_html}<div><div class="brand-title">GoAround <span class="sg-red">SG</span></div><div class="subtitle">AI local discovery assistant<br>for useful lobang near you.</div></div></div>
<div class="nav"><a class="{active('today')}" href="{make_url('today')}" target="_self">● GoAround Today</a><a class="{active('business')}" href="{make_url('business')}" target="_self">○ Business Promotion</a><a class="{active('about')}" href="{make_url('about')}" target="_self">○ What is GoAround?</a></div>
<div class="side-title">My area</div><div class="subtitle">Auto-detected when browser permission is allowed.</div>
<div class="info-card">
  <div class="info-row"><div class="info-icon">📍</div><div><div class="info-main">{safe_location}</div><div class="info-sub">{safe_location_source}</div></div></div>
  <div class="info-row"><div class="info-icon">{weather['icon']}</div><div><div class="info-main">{safe_weather_summary}</div><div class="info-sub">{safe_weather_source}</div></div></div>
  <div class="info-row"><div class="info-icon">◎</div><div><div class="info-main">{safe_radius_label}</div><div class="info-sub">{discovery_subtitle}</div></div></div>
  <div class="info-row"><div class="info-icon">🧭</div><div><div class="info-main">{safe_coords}</div><div class="info-sub">Approx. centre point</div></div></div>
</div>
<div class="small-note">No manual save is needed. Ask the chat about another place, for example: “What can I do near Chinatown?”</div>
<div class="sidebar-note">Source-backed. Verify details at source.</div>
<div class="footer" style="margin-top:15px; text-align:left; font-size:11px; line-height:1.4;">©2026 GoAroundSG.<br>Terms of Service. Privacy Policy</div>
''', unsafe_allow_html=True)


if page == "today":
    sidebar_col, picks_col, chat_col = st.columns([0.18, 0.56, 0.26], gap="medium")
    with sidebar_col:
        render_sidebar()
    with picks_col:
        with st.container(key="picks_card_container"):
            st.markdown('<div class="picks-card-marker"></div>', unsafe_allow_html=True)
            filter_options = [
                ("🌟 All", "all"),
                ("🍴 Food", "food"),
                ("🛒 Grocery", "grocery"),
                ("📅 Events", "event"),
                ("🏷️ Deals", "deal")
            ]
            
            if "active_filter" not in st.session_state:
                st.session_state["active_filter"] = "all"
                
            cols = st.columns(len(filter_options))
            for idx, (label, val) in enumerate(filter_options):
                is_active = (st.session_state["active_filter"] == val)
                if cols[idx].button(
                    label,
                    key=f"filter_btn_{val}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True
                ):
                    if st.session_state["active_filter"] != val:
                        st.session_state["active_filter"] = val
                        st.rerun()

            st.markdown(f'''
<div class="main-shell-title" style="margin-top: 14px; margin-bottom: 12px;">
  <div>
    <h1>Today’s Picks</h1>
    <div class="muted">Curated source-backed picks {safe_pick_scope}.</div>
  </div>
</div>
''', unsafe_allow_html=True)
            
            st.markdown(f'''
<div class="picklist" style="margin-top: 14px;">{picks_html}</div>
<div class="footer" style="color:#175CD3!important;font-weight:800; margin-top: 10px;">{safe_picks_footer}</div>
''', unsafe_allow_html=True)

    with chat_col:
        with st.container(key="chat_card_container"):
            st.markdown('<div class="chat-card-marker"></div>', unsafe_allow_html=True)
            st.markdown(f'''
<h1>Ask GoAround</h1><div class="muted">Your conversation-style local assistant.</div>
<div style="margin-top:12px; margin-bottom:12px;"><span class="status">{weather['icon']} {safe_weather_summary}</span><span class="status">📍 {safe_location}</span><span class="status">◎ {safe_radius_label}</span></div>
''', unsafe_allow_html=True)
            
            # Conversational state tracking
            if "ask_messages" not in st.session_state:
                st.session_state["ask_messages"] = [
                    {"role": "assistant", "content": "Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan."}
                ]
            
            def render_chat_history(include_thinking: bool = False) -> None:
                chat_history_html = ""
                for msg in st.session_state["ask_messages"][-6:]:
                    role = msg["role"]
                    content = escape(msg["content"]).replace("\n", "<br>")
                    if role == "user":
                        chat_history_html += f'<div style="text-align:right; margin: 10px 0;"><span class="bubble" style="background:#EAF2FF; text-align:left;">{content}</span> 👤</div>'
                    else:
                        chat_history_html += f'<div style="margin: 10px 0;">🤖 <span class="bubble">{content}</span></div>'
                if include_thinking:
                    chat_history_html += f'''
<div style="margin: 10px 0;">
  🤖 <span class="bubble" style="display: inline-flex; align-items: center; gap: 4px; padding: 12px 16px;">
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
  </span>
</div>
'''
                chat_placeholder.markdown(f'''
<div class="chatbox">
{chat_history_html}
</div>
''', unsafe_allow_html=True)
            
            chat_placeholder = st.empty()
            
            # Quick Actions using real Streamlit buttons inside container columns
            pending_prompt = None
            if len(st.session_state.get("ask_messages", [])) <= 1:
                prompts = [
                    ("🍴 Eat cheap", "Any cheap food spots near me?"),
                    ("📅 Weekend events", f"What weekend events are happening near {safe_location}?"),
                    ("🌧️ Rainy-day ideas", "What are some good rainy-day indoor ideas?"),
                    ("🛒 Grocery deals", "Are there any grocery deals or promos?")
                ]
                
                cols = st.columns(2)
                for idx, (label, query_text) in enumerate(prompts):
                    if cols[idx % 2].button(label, key=f"quick_{idx}", use_container_width=True):
                        pending_prompt = query_text
                    
            # Real input form with native text input that styles beautifully
            with st.form("ask_form", clear_on_submit=True):
                ic, sc = st.columns([9, 1])
                q_input = ic.text_input("Ask", placeholder="Ask GoAround about this area or another place...", label_visibility="collapsed")
                submitted = sc.form_submit_button("➤", use_container_width=True)
                
            st.markdown(f'''
<div class="footer" style="margin-top:10px;">Go Around can make mistakes. Please check details at the source</div>
''', unsafe_allow_html=True)
        
        # Processing user input
        user_query = pending_prompt or (q_input.strip() if submitted and q_input.strip() else None)
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
        else:
            render_chat_history()

elif page == "business":
    sidebar_col, form_col, preview_col = st.columns([0.18, 0.56, 0.26], gap="medium")
    with sidebar_col:
        render_sidebar()
    with form_col:
        with st.container(key="business_form_container"):
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
                
                publish_btn = st.form_submit_button("Publish Promotion", use_container_width=True)
                
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
        with st.container(key="preview_card_container"):
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
    sidebar_col, content_col = st.columns([0.18, 0.82], gap="medium")
    with sidebar_col:
        render_sidebar()
    with content_col:
        st.markdown(f'''
<div class="app-card full-card"><h1>What is GoAround SG?</h1><div class="muted">A source-backed local discovery assistant for Singapore. Current area scope: {safe_location} · {safe_radius_label}.</div>
<div class="about-section"><h2>For residents and visitors</h2><p>Ask what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan.</p></div><div class="about-section"><h2>For businesses</h2><p>Businesses can create local promotion cards that are shown to nearby users based on location, category, interests, and timing.</p></div><div class="about-section"><h2>Why it is different</h2><p>GoAround SG combines open data, source registries, browser location, weather, ranking, and AI conversation into one daily local assistant.</p></div><div class="about-section"><h2>Databricks usage in this prototype</h2><ul><li>Databricks Apps hosts the application.</li><li>Lakehouse / Delta can store Bronze, Silver, and Gold local discovery data.</li><li>Databricks SQL warehouse can serve candidate cards when configured.</li><li>Model Serving / GenAI can power Ask GoAround when a serving endpoint is configured.</li></ul></div><div class="footer">GoAround SG — Team R4131N. Source-backed local discovery. Verify final details at source.</div></div>
''', unsafe_allow_html=True)
