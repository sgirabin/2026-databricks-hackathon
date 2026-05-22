from __future__ import annotations

import os
import re
from typing import Any

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
from src.goaround.ranking import infer_time_of_day, rank_cards
from src.goaround.seed_data import area_anchor_cards, source_registry_cards

load_dotenv()
st.set_page_config(page_title="GoAround SG", page_icon="📍", layout="wide")

ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ONEMAP_REVERSE_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
MODES = ["Resident", "Worker/Student", "Visitor", "Considering moving here"]
INTERESTS = ["cheap food", "grocery", "deal", "event", "family", "fitness", "shopping", "transport", "local update", "tourist", "rainy day", "coffee", "weekend"]
PAGES = ["GoAround Today", "Business Promotion", "About Databricks"]

st.markdown("""
<style>
.main .block-container {padding-top:1.1rem; max-width:1500px; padding-bottom:.35rem;}
section[data-testid="stSidebar"] .block-container {padding-top:0rem;}
.brand-card {border:1px solid #e2e8f0;border-radius:18px;padding:12px;background:linear-gradient(135deg,#f8fafc,#eef6ff);margin-top:-18px;margin-bottom:10px;}
.brand-card h1 {font-size:22px;margin:0;color:#0f172a;line-height:1.1;}
.brand-card p {font-size:12px;color:#64748b;margin:6px 0 0 0;line-height:1.45;}
.status-line {border:1px solid #e5e7eb;border-radius:14px;padding:7px 10px;background:white;margin:0 0 8px 0;box-shadow:0 3px 10px rgba(15,23,42,.04);}
.status-title {font-size:13px;font-weight:800;color:#0f172a;margin-right:8px;}
.badge {display:inline-block;border-radius:999px;padding:3px 7px;font-size:11px;font-weight:700;margin:0 4px 3px 0;border:1px solid #dbeafe;background:#eff6ff;color:#1d4ed8;}
.badge-good {border-color:#bbf7d0;background:#f0fdf4;color:#15803d;}
.badge-warn {border-color:#fde68a;background:#fffbeb;color:#a16207;}
.chat-row {display:flex;margin:10px 0;}
.chat-row.assistant {justify-content:flex-start;}
.chat-row.user {justify-content:flex-end;}
.chat-bubble {max-width:78%;border-radius:16px;padding:10px 13px;font-size:14px;line-height:1.45;}
.chat-row.assistant .chat-bubble {background:#f1f5f9;color:#0f172a;border-bottom-left-radius:5px;}
.chat-row.user .chat-bubble {background:#2563eb;color:white;border-bottom-right-radius:5px;}
.chat-avatar {width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#eef2ff;margin-right:8px;flex:0 0 auto;}
div[data-testid="stVerticalBlock"] {gap:.32rem;}
</style>
""", unsafe_allow_html=True)

if "auto_location_attempted" not in st.session_state:
    st.session_state["auto_location_attempted"] = True
    st.session_state["request_browser_location"] = True


def esc(x: Any) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(x: Any) -> str:
    safe = esc(x)
    safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe)
    return safe.replace("\n", "<br>")


def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=25)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {"address": best.get("ADDRESS") or query, "lat": float(best["LATITUDE"]), "lon": float(best["LONGITUDE"])}


def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    # Use coordinate fallback for reliability in Databricks Apps.
    return {"address": f"Current location ({lat:.5f}, {lon:.5f})", "lat": lat, "lon": lon}


@st.cache_data(ttl=1800, show_spinner=False)
def weather_near(lat: float, lon: float) -> dict[str, Any]:
    try:
        data = requests.get(WEATHER_2H_URL, timeout=20).json()
        forecasts = {x["area"]: x.get("forecast") for x in data.get("items", [{}])[0].get("forecasts", [])}
        areas = data.get("area_metadata", [])
        best = min(areas, key=lambda a: abs(float(a["label_location"]["latitude"]) - lat) + abs(float(a["label_location"]["longitude"]) - lon))
        return {"area": best.get("name"), "forecast": forecasts.get(best.get("name"))}
    except Exception:
        return {"area": None, "forecast": None}


def weather_cards(weather: dict[str, Any], lat: float, lon: float, address: str) -> list[PickCard]:
    forecast = weather.get("forecast")
    if not forecast:
        return []
    return [PickCard(id="weather-now", card_type="local_update", category="weather", title=f"Weather near {weather.get('area') or address}: {forecast}", description="Weather-aware context for indoor/outdoor planning.", source_name="data.gov.sg Weather API", source_url="https://data.gov.sg/", lat=lat, lon=lon, location_name=address, tags=("weather", "rainy day", "resident", "visitor"), source_reliability=.9, freshness_score=.95)]


def render_pick(item, idx: int) -> None:
    card = item.card
    key = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{idx}-{card.id}")
    with st.container(border=True):
        st.markdown(f"**{card.title}**")
        st.caption(f"{card.category.title()} · score {item.score:.2f} · {card.source_name}")
        st.write(card.description)
        st.info(item.why_shown)
        c1, c2, c3, c4 = st.columns([.75, .75, .75, 1.45])
        if c1.button("💾", key=f"save-{key}", help="Save"):
            st.success("Saved.")
        if c2.button("↗️", key=f"share-{key}", help="Share"):
            st.code(f"{card.title}\n{card.description}\nSource: {card.source_url}")
        if c3.button("🔔", key=f"remind-{key}", help="Remind"):
            st.success("Reminder saved.")
        c4.link_button("Visit Website", card.source_url)


def render_chat(msg: dict[str, str]) -> None:
    role = msg.get("role", "assistant")
    avatar = "<div class='chat-avatar'>🤖</div>" if role == "assistant" else ""
    st.markdown(f"<div class='chat-row {role}'>{avatar}<div class='chat-bubble'>{md_to_html(msg.get('content', ''))}</div></div>", unsafe_allow_html=True)


def fallback_answer(ranked: list) -> str:
    if not ranked:
        return "I do not have enough source-backed cards yet. Try widening your radius."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} Open the source before acting."


with st.sidebar:
    st.markdown("<div class='brand-card'><h1>📍 GoAround SG</h1><p>AI local discovery assistant for useful lobang near you.</p></div>", unsafe_allow_html=True)
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    st.header("My area")
    mode = st.selectbox("I am here as", MODES)
    if st.session_state.get("request_browser_location") and get_geolocation is not None:
        loc = get_geolocation()
        coords = (loc or {}).get("coords") if isinstance(loc, dict) else None
        if coords:
            detected = reverse_geocode(float(coords["latitude"]), float(coords["longitude"]))
            st.session_state["detected_profile"] = detected
            st.session_state["saved_area"] = detected["address"]
            st.session_state["request_browser_location"] = False
        else:
            st.info("Allow browser location access, or use a custom location below.")
    sample = st.selectbox("Try location", ["Auto / Current location", "Custom", "308C Punggol Walk", "Chinatown MRT", "Orchard Road", "1 Tanjong Pagar Plaza"])
    if st.button("Detect current location again"):
        st.session_state["request_browser_location"] = True
        st.rerun()
    detected = st.session_state.get("detected_profile")
    if sample == "Auto / Current location" and detected:
        default_address = detected["address"]
    elif sample == "Custom":
        default_address = st.session_state.get("saved_area", "")
    elif sample == "Auto / Current location":
        default_address = st.session_state.get("saved_area", "Chinatown MRT")
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

if not address:
    st.info("Allow current location access, or enter a place, block or postal code to generate Today’s Picks.")
    st.stop()

try:
    profile = st.session_state.get("detected_profile") if address == st.session_state.get("detected_profile", {}).get("address") else geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

weather = weather_near(profile["lat"], profile["lon"])
lakehouse_cards = load_gold_candidate_cards()
lakehouse_mode = bool(lakehouse_cards)
genai_mode = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN") and os.getenv("DATABRICKS_MODEL_ENDPOINT"))

context = UserContext(mode=mode, address=profile["address"], lat=profile["lat"], lon=profile["lon"], radius_m=radius, interests=tuple(interests), time_of_day=infer_time_of_day(), weather=weather.get("forecast"))

cards: list[PickCard] = []
cards.extend(lakehouse_cards)
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=16)

if page == "GoAround Today":
    st.markdown(f"<div class='status-line'><span class='status-title'>Today</span><span class='badge {'badge-good' if lakehouse_mode else 'badge-warn'}'>Data: {'Lakehouse' if lakehouse_mode else 'Public/API'}</span><span class='badge {'badge-good' if genai_mode else 'badge-warn'}'>AI: {'Model Serving' if genai_mode else 'Safe fallback'}</span><span class='badge'>Area: {esc(profile['address'][:80])}</span><span class='badge'>Weather: {esc(weather.get('forecast') or 'n/a')}</span></div>", unsafe_allow_html=True)
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
        head, mode_badge = st.columns([3, 1])
        head.subheader("Ask GoAround")
        mode_badge.caption("Model Serving" if genai_mode else "Safe fallback")
        st.caption("Conversation-style local assistant grounded by source-backed Today’s Picks.")
        if "ask_messages" not in st.session_state:
            st.session_state["ask_messages"] = [{"role": "assistant", "content": "Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan."}]
        with st.container(height=620, border=True):
            for msg in st.session_state["ask_messages"]:
                render_chat(msg)
        with st.form("ask_goaround_form", clear_on_submit=True):
            input_col, send_col = st.columns([8, 1])
            question = input_col.text_input("Ask GoAround", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
            send = send_col.form_submit_button("➤", use_container_width=True)
        if st.button("Clear chat"):
            st.session_state["ask_messages"] = [{"role": "assistant", "content": "Chat cleared. What would you like to find nearby?"}]
            st.rerun()
        if send and question.strip():
            st.session_state["ask_messages"].append({"role": "user", "content": question.strip()})
            answer = answer_with_databricks(question.strip(), context, ranked, fallback_answer(ranked))
            st.session_state["ask_messages"].append({"role": "assistant", "content": answer})
            st.rerun()

elif page == "Business Promotion":
    st.subheader("Business Promotion Demo")
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

else:
    st.subheader("How GoAround SG uses Databricks")
    st.markdown("""
**Databricks Apps** runs the Streamlit experience on serverless app compute.

**Lakehouse / Delta** stores open-data entities as Bronze, Silver and Gold tables. The app reads `gold_candidate_cards` when Lakehouse mode is configured.

**Databricks SQL Warehouse** serves the Gold candidate cards to the app.

**Model Serving / GenAI** is supported through Databricks Model Serving when a serving endpoint is available; otherwise the app uses a safe source-grounded fallback.

**Lakebase-ready workflows** are represented by saved areas, reminders and business promotion submissions. In production, these interaction events can be persisted and used to improve ranking, analytics and business targeting.

```text
Open data + source registries
  -> Bronze Delta tables
  -> Silver cleaned local entities
  -> Gold candidate cards
  -> Today’s Picks ranking
  -> Ask GoAround assistant
```

Required Lakehouse environment variables:
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
