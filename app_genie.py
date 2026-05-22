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

CSS = """
<style>
.main .block-container {padding-top: 1.0rem; max-width: 1400px;}
.hero {border: 1px solid #e5e7eb; border-radius: 22px; padding: 18px 22px; background: linear-gradient(135deg,#f8fafc,#eef6ff); margin-bottom: 16px;}
.hero h1 {font-size: 30px; margin: 0; color: #0f172a;}
.hero p {margin: 6px 0 0 0; color: #475569;}
.badge {display:inline-block; border-radius:999px; padding:6px 11px; font-size:12px; font-weight:600; margin-right:8px; border:1px solid #dbeafe; background:#eff6ff; color:#1d4ed8;}
.badge-green {border-color:#bbf7d0; background:#f0fdf4; color:#15803d;}
.badge-amber {border-color:#fde68a; background:#fffbeb; color:#a16207;}
.pick-card {border:1px solid #e5e7eb; border-radius:18px; padding:16px; background:white; margin-bottom:12px; box-shadow:0 4px 12px rgba(15,23,42,0.04);}
.pick-title {font-weight:700; font-size:16px; color:#0f172a; margin-bottom:4px;}
.pick-meta {font-size:12px; color:#64748b; margin-bottom:8px;}
.why {background:#eff6ff; color:#1e3a8a; border-radius:12px; padding:9px 11px; font-size:13px; margin-top:8px;}
.chat-shell {border:1px solid #e5e7eb; border-radius:22px; background:#ffffff; min-height:620px; padding:0; overflow:hidden; box-shadow:0 8px 24px rgba(15,23,42,0.05);}
.chat-header {padding:16px 18px; border-bottom:1px solid #e5e7eb; background:#f8fafc; display:flex; align-items:center; justify-content:space-between;}
.chat-title {font-size:18px; font-weight:800; color:#0f172a; margin:0;}
.chat-subtitle {font-size:12px; color:#64748b; margin-top:2px;}
.chat-body {padding:20px; min-height:430px; max-height:560px; overflow-y:auto; background:linear-gradient(180deg,#ffffff,#fbfdff);}
.msg-row {display:flex; margin-bottom:16px;}
.msg-row.user {justify-content:flex-end;}
.msg-row.assistant {justify-content:flex-start;}
.avatar {width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin-right:9px; font-size:16px; background:#eef2ff;}
.bubble {max-width:78%; border-radius:18px; padding:12px 15px; line-height:1.48; font-size:14px;}
.user .bubble {background:#2563eb; color:white; border-bottom-right-radius:6px;}
.assistant .bubble {background:#f1f5f9; color:#0f172a; border-bottom-left-radius:6px;}
.prompt-chip {border:1px solid #dbeafe; background:#eff6ff; color:#1d4ed8; border-radius:999px; padding:7px 10px; font-size:12px; margin-right:6px; margin-bottom:8px; display:inline-block;}
.small-note {font-size:12px; color:#64748b;}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)


def html_escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(text: str) -> str:
    safe = html_escape(text)
    safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe)
    safe = safe.replace("\n", "<br>")
    return safe


def dist_label(v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    v = float(v)
    return f"{v:,.0f} m" if v < 1000 else f"{v/1000:.1f} km"


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
        block, road = info.get("BLOCK") or "", info.get("ROAD") or info.get("ROAD_NAME") or ""
        building, postal = info.get("BUILDINGNAME") or info.get("BUILDING") or "", info.get("POSTALCODE") or info.get("POSTAL") or ""
        address = " ".join([block, road, building, postal]).strip() or fallback["address"]
        return {**fallback, "address": address, "postal_code": postal, "road_name": road}
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
def load_public_open_data_cards(lat: float, lon: float, radius_m: int) -> list[PickCard]:
    frames = [load_geojson_points(dataset_id, category) for category, dataset_id in DATASETS.items()]
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
    if df.empty:
        return []
    df["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in df.itertuples()]
    df = df[df.distance_m <= radius_m].sort_values("distance_m").head(40)
    cards = []
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


def default_fallback_answer(ranked: list) -> str:
    if not ranked:
        return "I do not have enough source-backed cards yet. Try widening your radius."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} {top.why_shown} Open the source before acting."


def render_pick(item, idx: int) -> None:
    card = item.card
    distance = "" if item.distance_m is None else f" · {dist_label(item.distance_m)}"
    st.markdown(f"""
<div class='pick-card'>
  <div class='pick-title'>{html_escape(card.title)}</div>
  <div class='pick-meta'>{html_escape(card.category.title())}{distance} · score {item.score:.2f} · {html_escape(card.source_name)}</div>
  <div>{html_escape(card.description)}</div>
  <div class='why'>{html_escape(item.why_shown)}</div>
</div>
""", unsafe_allow_html=True)


def render_chat(messages: list[dict[str, str]]) -> None:
    st.markdown("<div class='chat-body'>", unsafe_allow_html=True)
    for message in messages:
        role = message["role"]
        avatar = "🧑" if role == "user" else "🤖"
        st.markdown(f"""
<div class='msg-row {role}'>
  {'' if role == 'user' else f"<div class='avatar'>{avatar}</div>"}
  <div class='bubble'>{md_to_html(message['content'])}</div>
</div>
""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------- UI -----------------------------

st.markdown("""
<div class='hero'>
  <h1>📍 GoAround SG</h1>
  <p>AI local discovery assistant for useful lobang near where people live, work, study, or visit.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("My area")
    mode = st.selectbox("I am here as", MODES)
    sample = st.selectbox("Try location", ["Custom", "308C Punggol Walk", "83 Punggol Central", "Chinatown MRT", "Orchard Road", "1 Tanjong Pagar Plaza"])
    if st.button("Use my current location"):
        st.session_state["request_browser_location"] = True
    if st.session_state.get("request_browser_location"):
        if get_geolocation is None:
            st.warning("Browser geolocation helper unavailable. Use manual search.")
        else:
            loc = get_geolocation()
            coords = (loc or {}).get("coords") if isinstance(loc, dict) else None
            if coords:
                detected = reverse_geocode(float(coords["latitude"]), float(coords["longitude"]))
                st.session_state["detected_profile"] = detected
                st.session_state["saved_area"] = detected["address"]
                st.session_state["request_browser_location"] = False
                st.success(f"Detected: {detected['address']}")
    detected_profile = st.session_state.get("detected_profile")
    default_address = detected_profile["address"] if detected_profile else (st.session_state.get("saved_area", "") if sample == "Custom" else sample)
    address = st.text_input("Block / place / postal code", default_address)
    radius = st.slider("Discovery radius", 500, 3000, int(st.session_state.get("radius", 1500)), 100)
    interests = st.multiselect("Interests", INTERESTS, default=st.session_state.get("interests", ["cheap food", "grocery", "event", "deal"]))
    if st.button("Save my area"):
        st.session_state["saved_area"] = address
        st.session_state["radius"] = radius
        st.session_state["interests"] = interests
        st.success("Saved for this session. In production this goes to Lakebase.")

if not address and not st.session_state.get("detected_profile"):
    st.info("Enter a place, block or postal code to generate Today’s Picks.")
    st.stop()

try:
    profile = st.session_state["detected_profile"] if st.session_state.get("detected_profile") and address == st.session_state["detected_profile"]["address"] else geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

with st.spinner("Building source-backed local context..."):
    lakehouse_cards = load_gold_candidate_cards()
    lakehouse_mode = bool(lakehouse_cards)
    public_cards = [] if lakehouse_mode else load_public_open_data_cards(profile["lat"], profile["lon"], radius)
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

badge_data = "Lakehouse" if lakehouse_mode else "Public API fallback"
badge_ai = "Model Serving GenAI" if genai_mode else "Safe fallback"
st.markdown(f"""
<span class='badge {'badge-green' if lakehouse_mode else 'badge-amber'}'>Data mode: {badge_data}</span>
<span class='badge {'badge-green' if genai_mode else 'badge-amber'}'>AI mode: {badge_ai}</span>
<span class='badge'>Area: {html_escape(profile['address'][:80])}</span>
<span class='badge'>Weather: {html_escape(weather.get('forecast') or 'n/a')}</span>
""", unsafe_allow_html=True)

left, right = st.columns([0.95, 1.35], gap="large")

with left:
    st.subheader("Today’s Picks")
    st.caption("Ranked cards from Lakehouse/open data, source registries, weather, location and interests.")
    if not ranked:
        st.warning("No source-backed picks found. Try widening the radius.")
    for idx, item in enumerate(ranked[:8]):
        render_pick(item, idx)

with right:
    st.markdown("<div class='chat-shell'>", unsafe_allow_html=True)
    st.markdown(f"""
<div class='chat-header'>
  <div>
    <div class='chat-title'>Ask GoAround</div>
    <div class='chat-subtitle'>Genie-style local assistant grounded by source-backed Today’s Picks</div>
  </div>
  <div class='small-note'>{'Databricks Model Serving' if genai_mode else 'Safe fallback mode'}</div>
</div>
""", unsafe_allow_html=True)

    if "ask_messages" not in st.session_state:
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan."}]

    render_chat(st.session_state["ask_messages"])

    chips = [
        "what to eat today?",
        "what can I do with my kid this weekend?",
        "I am visiting this area for 2 hours",
        "any rainy-day options nearby?",
    ]
    st.markdown("<div style='padding:0 20px 8px 20px'>", unsafe_allow_html=True)
    chip_cols = st.columns(2)
    for i, chip in enumerate(chips):
        if chip_cols[i % 2].button(chip, key=f"chip-{i}"):
            st.session_state["pending_prompt"] = chip
            st.rerun()
    if st.button("Clear chat", key="clear-chat-main"):
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Chat cleared. What would you like to find nearby?"}]
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input("Ask GoAround about this area...")
    prompt = st.session_state.pop("pending_prompt", None) or prompt
    if prompt:
        st.session_state["ask_messages"].append({"role": "user", "content": prompt})
        answer = answer_with_databricks(prompt, context, ranked, default_fallback_answer(ranked))
        st.session_state["ask_messages"].append({"role": "assistant", "content": answer})
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

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

Run `databricks/setup_open_data_delta.py` to create Bronze, Silver and Gold Delta tables.

Lakehouse env vars:
```text
USE_DATABRICKS_SQL=true
GOAROUND_CATALOG=main
GOAROUND_SCHEMA=goaround_sg
DATABRICKS_SERVER_HOSTNAME=<serverless SQL hostname>
DATABRICKS_HTTP_PATH=<serverless SQL warehouse HTTP path>
DATABRICKS_TOKEN=<token or secret>
```

GenAI env vars:
```text
DATABRICKS_HOST=https://<workspace-url>
DATABRICKS_MODEL_ENDPOINT=<serving-endpoint-name>
DATABRICKS_TOKEN=<token or secret>
```
""")

st.caption("GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.")
