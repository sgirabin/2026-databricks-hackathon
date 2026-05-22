from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

try:
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = None

from src.goaround.agent import answer_with_databricks
from src.goaround.business import create_business_promo_card
from src.goaround.lakehouse import load_gold_candidate_cards
from src.goaround.models import PickCard, UserContext
from src.goaround.ranking import haversine_m, infer_time_of_day, rank_cards
from src.goaround.seed_data import area_anchor_cards, source_registry_cards

load_dotenv()
st.set_page_config(page_title="GoAround SG", page_icon="📍", layout="wide")

ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ONEMAP_REVERSE_URL = "https://www.onemap.gov.sg/api/public/revgeocode"
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"

DATASETS = {
    "hawker_centres": "d_4a086da0a5553be1d89383cd90d07ecd",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
}
MODES = ["Resident", "Worker/Student", "Visitor", "Considering moving here"]
INTERESTS = ["cheap food", "grocery", "deal", "event", "family", "fitness", "shopping", "transport", "local update", "tourist", "rainy day", "coffee", "weekend"]

st.markdown(
    """
<style>
.main .block-container {padding-top: 0.7rem; max-width: 1500px; padding-bottom: 0.5rem;}
section[data-testid="stSidebar"] .block-container {padding-top: 1.2rem;}
.brand-card {border:1px solid #e2e8f0; border-radius:18px; padding:14px; background:linear-gradient(135deg,#f8fafc,#eef6ff); margin-bottom:16px;}
.brand-card h1 {font-size:22px; margin:0; color:#0f172a;}
.brand-card p {font-size:12px; color:#64748b; margin:6px 0 0 0;}
.status-card {border:1px solid #e5e7eb; border-radius:18px; padding:12px 16px; background:white; margin-bottom:10px; box-shadow:0 4px 12px rgba(15,23,42,0.04);}
.status-card h2 {font-size:20px; margin:0 0 8px 0; color:#0f172a;}
.badge {display:inline-block; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:700; margin:0 6px 6px 0; border:1px solid #dbeafe; background:#eff6ff; color:#1d4ed8;}
.badge-good {border-color:#bbf7d0; background:#f0fdf4; color:#15803d;}
.badge-warn {border-color:#fde68a; background:#fffbeb; color:#a16207;}
.small-note {font-size:12px; color:#64748b;}
.pick-title {font-weight:750; font-size:15px; color:#0f172a; margin-bottom:4px;}
.pick-meta {font-size:12px; color:#64748b; margin-bottom:8px;}
/* keep the whole app compact for recording */
div[data-testid="stVerticalBlock"] {gap: 0.45rem;}
</style>
""",
    unsafe_allow_html=True,
)

# Automatically attempt browser location detection on first load/reload.
# Browsers still require explicit user permission; manual location remains available.
if "auto_location_attempted" not in st.session_state:
    st.session_state["auto_location_attempted"] = True
    st.session_state["request_browser_location"] = True


def esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value)


def dist_label(v: Any) -> str:
    if v is None or pd.isna(v):
        return ""
    v = float(v)
    return f" · {v:,.0f}m" if v < 1000 else f" · {v/1000:.1f}km"


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=25)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {"address": best.get("ADDRESS") or query, "postal_code": best.get("POSTAL") or "", "road_name": best.get("ROAD_NAME") or "", "lat": float(best["LATITUDE"]), "lon": float(best["LONGITUDE"])}


@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    fallback = {"address": f"Current location ({lat:.5f}, {lon:.5f})", "postal_code": "", "road_name": "", "lat": lat, "lon": lon}
    try:
        r = requests.get(ONEMAP_REVERSE_URL, params={"location": f"{lat},{lon}", "buffer": 80, "addressType": "All"}, timeout=20)
        r.raise_for_status()
        info = (r.json().get("GeocodeInfo") or [{}])[0]
        address = " ".join([info.get("BLOCK") or "", info.get("ROAD") or info.get("ROAD_NAME") or "", info.get("BUILDINGNAME") or info.get("BUILDING") or "", info.get("POSTALCODE") or info.get("POSTAL") or ""]).strip()
        return {**fallback, "address": address or fallback["address"], "postal_code": info.get("POSTALCODE") or info.get("POSTAL") or "", "road_name": info.get("ROAD") or info.get("ROAD_NAME") or ""}
    except Exception:
        return fallback


@st.cache_data(ttl=86400, show_spinner=False)
def poll_download_url(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


@st.cache_data(ttl=86400, show_spinner=False)
def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    try:
        gj = requests.get(poll_download_url(dataset_id), timeout=90).json()
        rows = []
        for feature in gj.get("features", []):
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or []
            props = feature.get("properties") or {}
            if geom.get("type") == "Point" and len(coords) >= 2:
                name = props.get("NAME") or props.get("Name") or props.get("ADDRESSBUILDINGNAME") or props.get("DESCRIPTION") or category
                rows.append({"category": category, "name": str(name), "lat": float(coords[1]), "lon": float(coords[0]), "source": "data.gov.sg"})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["category", "name", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=True)
def load_public_cards(lat: float, lon: float, radius_m: int) -> list[PickCard]:
    frames = [load_geojson_points(dataset_id, category) for category, dataset_id in DATASETS.items()]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
    if df.empty:
        return []
    df["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in df.itertuples()]
    df = df[df.distance_m <= radius_m].sort_values("distance_m").head(40)
    cards: list[PickCard] = []
    for row in df.itertuples():
        cat = str(row.category)
        card_type = "food" if cat == "hawker_centres" else "deal" if cat == "supermarkets" else "event"
        tags = {"hawker_centres": ("food", "cheap food", "lunch", "dinner", "tourist", "resident"), "supermarkets": ("grocery", "shopping", "deal", "resident"), "community_clubs": ("community", "event", "family", "weekend", "resident")}.get(cat, (cat,))
        cards.append(PickCard(id=f"api-{cat}-{abs(hash((row.name, row.lat, row.lon))) % 999999}", card_type=card_type, category=cat, title=str(row.name), description=f"Nearby {cat.replace('_', ' ')} from data.gov.sg open data.", source_name="data.gov.sg open data API", source_url="https://data.gov.sg/", lat=float(row.lat), lon=float(row.lon), location_name=str(row.name), tags=tags, source_reliability=0.82, freshness_score=0.55))
    return cards


@st.cache_data(ttl=1800, show_spinner=False)
def weather_near(lat: float, lon: float) -> dict[str, Any]:
    try:
        data = requests.get(WEATHER_2H_URL, timeout=20).json()
        forecasts = {x["area"]: x.get("forecast") for x in data.get("items", [{}])[0].get("forecasts", [])}
        best = None
        for area in data.get("area_metadata", []):
            loc = area.get("label_location") or {}
            d = haversine_m(lat, lon, float(loc.get("latitude")), float(loc.get("longitude")))
            if best is None or d < best[0]:
                best = (d, area.get("name"))
        return {"area": best[1], "forecast": forecasts.get(best[1])} if best else {"area": None, "forecast": None}
    except Exception:
        return {"area": None, "forecast": None}


def weather_cards(weather: dict[str, Any], lat: float, lon: float, area_name: str) -> list[PickCard]:
    forecast = weather.get("forecast")
    if not forecast:
        return []
    tags = ["weather", "resident", "visitor"]
    if any(x in forecast.lower() for x in ["rain", "showers", "thundery"]):
        tags += ["rainy day", "indoor", "transport"]
    return [PickCard(id="weather-now", card_type="local_update", category="weather", title=f"Weather near {weather.get('area') or area_name}: {forecast}", description="Weather-aware context for indoor/outdoor planning.", source_name="data.gov.sg Weather API", source_url="https://data.gov.sg/", lat=lat, lon=lon, location_name=area_name, tags=tuple(tags), source_reliability=0.9, freshness_score=0.95)]


def default_answer(ranked: list) -> str:
    if not ranked:
        return "I do not have enough source-backed cards yet. Try widening your radius."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} Open the source before acting."


def render_pick(item, idx: int) -> None:
    card = item.card
    key = safe_key(f"{idx}-{card.id}")
    with st.container(border=True):
        st.markdown(f"**{card.title}**")
        st.caption(f"{card.category.title()}{dist_label(item.distance_m)} · score {item.score:.2f} · {card.source_name}")
        st.write(card.description)
        st.info(item.why_shown)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
        if c1.button("Save", key=f"save-{key}"):
            st.session_state.setdefault("saved_cards", []).append(card.id)
            st.success("Saved.")
        if c2.button("Share", key=f"share-{key}"):
            st.code(f"{card.title}\n{card.description}\nSource: {card.source_url}")
        if c3.button("Remind", key=f"remind-{key}"):
            st.session_state.setdefault("reminders", []).append(card.id)
            st.success("Reminder saved.")
        c4.link_button("Open source", card.source_url)


with st.sidebar:
    st.markdown("""
<div class='brand-card'>
  <h1>📍 GoAround SG</h1>
  <p>AI local discovery assistant for useful lobang near you.</p>
</div>
""", unsafe_allow_html=True)
    st.header("My area")
    mode = st.selectbox("I am here as", MODES)

    if st.session_state.get("request_browser_location"):
        if get_geolocation is None:
            st.warning("Browser geolocation helper unavailable. Use manual search.")
            st.session_state["request_browser_location"] = False
        else:
            loc = get_geolocation()
            coords = (loc or {}).get("coords") if isinstance(loc, dict) else None
            if coords:
                detected = reverse_geocode(float(coords["latitude"]), float(coords["longitude"]))
                st.session_state["detected_profile"] = detected
                st.session_state["saved_area"] = detected["address"]
                st.session_state["request_browser_location"] = False
                st.success(f"Detected: {detected['address']}")
            else:
                st.info("Allow browser location access, or use a custom location below.")

    detected_profile = st.session_state.get("detected_profile")
    location_options = ["Auto / Current location", "Custom", "308C Punggol Walk", "83 Punggol Central", "Chinatown MRT", "Orchard Road", "1 Tanjong Pagar Plaza"]
    sample = st.selectbox("Try location", location_options)
    if st.button("Detect current location again"):
        st.session_state["request_browser_location"] = True
        st.rerun()

    if sample == "Auto / Current location" and detected_profile:
        default_address = detected_profile["address"]
    elif sample == "Auto / Current location":
        default_address = st.session_state.get("saved_area", "Chinatown MRT")
    elif sample == "Custom":
        default_address = st.session_state.get("saved_area", "")
    else:
        default_address = sample

    address = st.text_input("Block / place / postal code", default_address)
    radius = st.slider("Discovery radius", 500, 3000, int(st.session_state.get("radius", 1500)), 100)
    interests = st.multiselect("Interests", INTERESTS, default=st.session_state.get("interests", ["cheap food", "grocery", "event", "deal"]))
    if st.button("Save my area"):
        st.session_state["saved_area"] = address
        st.session_state["radius"] = radius
        st.session_state["interests"] = interests
        st.success("Saved for this session. In production this goes to Lakebase.")

if not address and not st.session_state.get("detected_profile"):
    st.info("Allow current location access or enter a place, block or postal code to generate Today’s Picks.")
    st.stop()

try:
    profile = st.session_state["detected_profile"] if st.session_state.get("detected_profile") and address == st.session_state["detected_profile"]["address"] else geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

with st.spinner("Building source-backed local context..."):
    lakehouse_cards = load_gold_candidate_cards()
    lakehouse_mode = bool(lakehouse_cards)
    public_cards = [] if lakehouse_mode else load_public_cards(profile["lat"], profile["lon"], radius)
    weather = weather_near(profile["lat"], profile["lon"])

context = UserContext(mode=mode, address=profile["address"], lat=profile["lat"], lon=profile["lon"], radius_m=radius, interests=tuple(interests), time_of_day=infer_time_of_day(), weather=weather.get("forecast"))

cards: list[PickCard] = []
cards.extend(lakehouse_cards if lakehouse_mode else public_cards)
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=16)

genai_mode = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN") and os.getenv("DATABRICKS_MODEL_ENDPOINT"))

st.markdown(f"""
<div class='status-card'>
  <h2>Today around your area</h2>
  <span class='badge {'badge-good' if lakehouse_mode else 'badge-warn'}'>Data mode: {'Lakehouse' if lakehouse_mode else 'Public API fallback'}</span>
  <span class='badge {'badge-good' if genai_mode else 'badge-warn'}'>AI mode: {'Model Serving GenAI' if genai_mode else 'Safe fallback'}</span>
  <span class='badge'>Area: {esc(profile['address'][:90])}</span>
  <span class='badge'>Weather: {esc(weather.get('forecast') or 'n/a')}</span>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([0.95, 1.35], gap="large")

with left:
    st.subheader("Today’s Picks")
    st.caption("Ranked from Lakehouse/open data, source registries, weather, location and interests.")
    with st.container(height=710, border=False):
        if not ranked:
            st.warning("No source-backed picks found. Try widening the radius.")
        for idx, item in enumerate(ranked[:12]):
            render_pick(item, idx)

with right:
    header_col, mode_col = st.columns([3, 1])
    header_col.subheader("Ask GoAround")
    mode_col.caption("Model Serving" if genai_mode else "Safe fallback")
    st.caption("Conversation-style local assistant grounded by source-backed Today’s Picks.")

    if "ask_messages" not in st.session_state:
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan."}]

    with st.container(height=570, border=True):
        for msg in st.session_state["ask_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.form("ask_goaround_form", clear_on_submit=True):
        user_question = st.text_input("Ask GoAround about this area", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
        send = st.form_submit_button("Send", use_container_width=True)

    chip_cols = st.columns(4)
    examples = ["what to eat today?", "what can I do with my kid this weekend?", "I am visiting this area for 2 hours", "any rainy-day options nearby?"]
    for i, example in enumerate(examples):
        if chip_cols[i].button(example, key=f"chip-{i}"):
            st.session_state["pending_prompt"] = example
            st.rerun()
    if st.button("Clear chat", key="clear-chat"):
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Chat cleared. What would you like to find nearby?"}]
        st.rerun()

prompt = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
if send and user_question.strip():
    prompt = user_question.strip()

if prompt:
    st.session_state["ask_messages"].append({"role": "user", "content": prompt})
    answer = answer_with_databricks(prompt, context, ranked, default_answer(ranked))
    st.session_state["ask_messages"].append({"role": "assistant", "content": answer})
    st.rerun()

with st.expander("Business promotion demo"):
    st.caption("Creates a source-backed local promotion card. Production version stores this in Lakebase.")
    with st.form("business_promo"):
        business_name = st.text_input("Business name", "Sample Cafe")
        promo_title = st.text_input("Promotion title", "Lunch set promo near you")
        promo_desc = st.text_area("Description", "Source-backed local promotion. Verify terms at source.")
        category = st.selectbox("Category", ["food", "grocery", "mall", "fitness", "family", "tourist", "service"])
        source_url = st.text_input("Source URL", "https://example.com/promo")
        valid_until = st.date_input("Valid until")
        tags = st.multiselect("Target tags", INTERESTS, default=["deal", "cheap food"])
        submitted = st.form_submit_button("Create promotion card")
    if submitted:
        if not source_url.startswith("http"):
            st.error("A valid source URL is required. No source URL = no claim.")
        else:
            card = create_business_promo_card(business_name=business_name, title=promo_title, description=promo_desc, category=category, source_url=source_url, lat=profile["lat"], lon=profile["lon"], location_name=profile["address"], valid_until=str(valid_until), tags=tags)
            st.session_state.setdefault("business_cards", []).append(card)
            st.success("Promotion created. It will appear in Today’s Picks after rerun if relevant.")

with st.expander("Data & Databricks integration"):
    st.markdown("""
- **Databricks Apps** runs this Streamlit app on serverless app compute.
- **Lakehouse mode** reads `gold_candidate_cards` through Databricks SQL when configured.
- **Generative AI mode** sends Ask GoAround questions to Databricks Model Serving when configured.
- **Fallback mode** keeps the app usable without credentials.

Lakehouse env vars:
```text
USE_DATABRICKS_SQL=true
GOAROUND_CATALOG=workspace
GOAROUND_SCHEMA=goaround_sg
DATABRICKS_SERVER_HOSTNAME=<serverless SQL hostname>
DATABRICKS_HTTP_PATH=<serverless SQL warehouse HTTP path>
DATABRICKS_TOKEN=<token or secret>
```
""")

st.caption("GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.")
