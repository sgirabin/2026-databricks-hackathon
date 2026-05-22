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
except Exception:  # optional browser helper
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
INTERESTS = [
    "cheap food", "grocery", "deal", "event", "family", "fitness", "shopping",
    "transport", "local update", "tourist", "rainy day", "coffee", "weekend"
]


def dist_label(v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    v = float(v)
    return f"{v:,.0f} m" if v < 1000 else f"{v/1000:.1f} km"


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(
        ONEMAP_SEARCH_URL,
        params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
        timeout=25,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {
        "address": best.get("ADDRESS") or query,
        "postal_code": best.get("POSTAL") or "",
        "road_name": best.get("ROAD_NAME") or "",
        "lat": float(best["LATITUDE"]),
        "lon": float(best["LONGITUDE"]),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    fallback = {
        "address": f"Current location ({lat:.5f}, {lon:.5f})",
        "postal_code": "",
        "road_name": "",
        "lat": float(lat),
        "lon": float(lon),
    }
    try:
        r = requests.get(
            ONEMAP_REVERSE_URL,
            params={"location": f"{lat},{lon}", "buffer": 80, "addressType": "All"},
            timeout=20,
        )
        r.raise_for_status()
        info = (r.json().get("GeocodeInfo") or [{}])[0]
        block = info.get("BLOCK") or ""
        road = info.get("ROAD") or info.get("ROAD_NAME") or ""
        building = info.get("BUILDINGNAME") or info.get("BUILDING") or ""
        postal = info.get("POSTALCODE") or info.get("POSTAL") or ""
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
            if geom.get("type") != "Point" or len(coords) < 2:
                continue
            name = props.get("NAME") or props.get("Name") or props.get("ADDRESSBUILDINGNAME") or props.get("DESCRIPTION") or category
            rows.append({
                "category": category,
                "name": str(name),
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "source": "data.gov.sg",
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["category", "name", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=True)
def load_public_open_data_cards(lat: float, lon: float, radius_m: int) -> list[PickCard]:
    frames = []
    for category, dataset_id in DATASETS.items():
        frames.append(load_geojson_points(dataset_id, category))
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True) if any(not f.empty for f in frames) else pd.DataFrame()
    if df.empty:
        return []
    df["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in df.itertuples()]
    df = df[df.distance_m <= radius_m].sort_values("distance_m").head(40)
    cards = []
    for row in df.itertuples():
        cat = str(row.category)
        card_type = "food" if cat == "hawker_centres" else "deal" if cat == "supermarkets" else "event"
        tags = {
            "hawker_centres": ("food", "cheap food", "lunch", "dinner", "tourist", "resident"),
            "supermarkets": ("grocery", "shopping", "deal", "resident"),
            "community_clubs": ("community", "event", "family", "weekend", "resident"),
        }.get(cat, (cat,))
        cards.append(PickCard(
            id=f"api-{cat}-{abs(hash((row.name, row.lat, row.lon))) % 999999}",
            card_type=card_type,
            category=cat,
            title=str(row.name),
            description=f"Nearby {cat.replace('_', ' ')} from data.gov.sg open data.",
            source_name="data.gov.sg open data API",
            source_url="https://data.gov.sg/",
            lat=float(row.lat),
            lon=float(row.lon),
            location_name=str(row.name),
            tags=tags,
            source_reliability=0.82,
            freshness_score=0.55,
        ))
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
        if best:
            return {"area": best[1], "forecast": forecasts.get(best[1])}
    except Exception:
        pass
    return {"area": None, "forecast": None}


def weather_cards(weather: dict[str, Any], lat: float, lon: float, area_name: str) -> list[PickCard]:
    forecast = weather.get("forecast")
    if not forecast:
        return []
    tags = ["weather", "resident", "visitor"]
    if any(x in forecast.lower() for x in ["rain", "showers", "thundery"]):
        tags += ["rainy day", "indoor", "transport"]
    return [PickCard(
        id="weather-now",
        card_type="local_update",
        category="weather",
        title=f"Weather near {weather.get('area') or area_name}: {forecast}",
        description="Weather-aware context for indoor/outdoor planning.",
        source_name="data.gov.sg Weather API",
        source_url="https://data.gov.sg/",
        lat=lat,
        lon=lon,
        location_name=area_name,
        tags=tuple(tags),
        source_reliability=0.9,
        freshness_score=0.95,
    )]


def default_fallback_answer(ranked: list) -> str:
    if not ranked:
        return "I do not have enough source-backed cards yet. Try widening your radius."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} {top.why_shown} Open the source before acting."


def icon_for(card_type: str) -> str:
    return {"deal": "🔥", "food": "🍜", "event": "🎟", "transport": "🚌", "local_update": "🏘", "plan": "🧭"}.get(card_type, "📍")


def render_card(item, key_prefix: str) -> None:
    card = item.card
    safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{key_prefix}-{card.id}")
    distance = "" if item.distance_m is None else f" · {dist_label(item.distance_m)}"
    with st.container(border=True):
        st.markdown(f"### {icon_for(card.card_type)} {card.title}")
        st.caption(f"{card.category.title()}{distance} · score {item.score:.2f}")
        st.write(card.description)
        st.info(item.why_shown)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
        if c1.button("Save", key=f"save-{safe_key}"):
            st.session_state.setdefault("saved_cards", []).append(card.id)
            st.success("Saved.")
        if c2.button("Share", key=f"share-{safe_key}"):
            st.code(f"{card.title}\n{card.description}\nSource: {card.source_url}")
        if c3.button("Remind", key=f"remind-{safe_key}"):
            st.session_state.setdefault("reminders", []).append(card.id)
            st.success("Reminder saved.")
        c4.link_button("Open source", card.source_url)


# ----------------------------- App -----------------------------

st.title("📍 GoAround SG")
st.caption("Databricks-integrated AI local discovery app: Lakehouse-backed Today’s Picks + Generative AI Ask GoAround.")

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

with st.spinner("Building Lakehouse-backed Today’s Picks..."):
    lakehouse_cards = load_gold_candidate_cards()
    lakehouse_mode = bool(lakehouse_cards)
    public_cards = [] if lakehouse_mode else load_public_open_data_cards(profile["lat"], profile["lon"], radius)
    weather = weather_near(profile["lat"], profile["lon"])

context = UserContext(
    mode=mode,
    address=profile["address"],
    lat=profile["lat"],
    lon=profile["lon"],
    radius_m=radius,
    interests=tuple(interests),
    time_of_day=infer_time_of_day(),
    weather=weather.get("forecast"),
)

cards: list[PickCard] = []
cards.extend(lakehouse_cards if lakehouse_mode else public_cards)
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=16)

genai_mode = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN") and os.getenv("DATABRICKS_MODEL_ENDPOINT"))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Data mode", "Lakehouse" if lakehouse_mode else "Public API fallback")
m2.metric("GenAI mode", "Model Serving" if genai_mode else "Safe fallback")
m3.metric("Today’s Picks", len(ranked))
m4.metric("Weather", weather.get("forecast") or "n/a")

if not lakehouse_mode:
    st.warning("Lakehouse cards are not enabled yet. The app is using public open-data APIs as fallback. Set USE_DATABRICKS_SQL=true and SQL warehouse variables to use Delta gold_candidate_cards.")
if not genai_mode:
    st.warning("Databricks Model Serving is not configured yet. Ask GoAround will use safe local fallback. Set DATABRICKS_HOST, DATABRICKS_TOKEN, and DATABRICKS_MODEL_ENDPOINT to use Generative AI.")

tab_today, tab_ask, tab_business, tab_data = st.tabs(["Today’s Picks", "Ask GoAround", "Business Demo", "Data & Databricks"])

with tab_today:
    st.subheader("Today’s Picks Near You")
    st.caption(f"{profile['address']} · {radius}m · {mode} · {context.time_of_day.title()} · {'Lakehouse-backed' if lakehouse_mode else 'API fallback'}")
    for idx, item in enumerate(ranked[:10]):
        render_card(item, f"today-{idx}")

with tab_ask:
    st.subheader("Ask GoAround")
    st.caption("Chat assistant. Uses Databricks Model Serving when configured; otherwise safe intent fallback.")
    if "ask_messages" not in st.session_state:
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Hi, I’m Ask GoAround. Ask me what to eat, what to do, what deals are nearby, or how to plan a short visit."}]
    if st.button("Clear chat"):
        st.session_state["ask_messages"] = [{"role": "assistant", "content": "Chat cleared. What would you like to find nearby?"}]
    st.markdown("**Try:** `what to eat today?` · `what can I do with my kid this weekend?` · `I am visiting this area for 2 hours`")
    for message in st.session_state["ask_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    prompt = st.chat_input("Ask GoAround about this area...")
    if prompt:
        st.session_state["ask_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        answer = answer_with_databricks(prompt, context, ranked, default_fallback_answer(ranked))
        st.session_state["ask_messages"].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

with tab_business:
    st.subheader("Business Promotion Demo")
    st.caption("Business-submitted cards demonstrate Lakebase-ready hyperlocal promotion.")
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
            card = create_business_promo_card(
                business_name=business_name,
                title=promo_title,
                description=promo_desc,
                category=category,
                source_url=source_url,
                lat=profile["lat"],
                lon=profile["lon"],
                location_name=profile["address"],
                valid_until=str(valid_until),
                tags=tags,
            )
            st.session_state.setdefault("business_cards", []).append(card)
            st.success("Promotion created. It will appear in Today’s Picks after rerun if relevant.")

with tab_data:
    st.subheader("Data & Databricks Integration")
    st.markdown("""
### What is active in this branch

- **Databricks Apps** runs this Streamlit application on serverless app compute.
- **Lakehouse / Delta optional mode** reads `gold_candidate_cards` through Databricks SQL when configured.
- **Generative AI optional mode** sends Ask GoAround questions to Databricks Model Serving when configured.
- **Fallback mode** keeps the app usable without credentials.

### Required Lakehouse setup

Run:

```text
databricks/setup_open_data_delta.py
```

It creates:

```text
bronze_hawker_centres
bronze_supermarkets
bronze_community_clubs
silver_local_entities
silver_source_registry
gold_candidate_cards
```

### Required app environment variables for Lakehouse mode

```text
USE_DATABRICKS_SQL=true
GOAROUND_CATALOG=main
GOAROUND_SCHEMA=goaround_sg
DATABRICKS_SERVER_HOSTNAME=<serverless SQL hostname>
DATABRICKS_HTTP_PATH=<serverless SQL warehouse HTTP path>
DATABRICKS_TOKEN=<token or secret>
```

### Required app environment variables for Generative AI mode

```text
DATABRICKS_HOST=https://<workspace-url>
DATABRICKS_MODEL_ENDPOINT=<serving-endpoint-name>
DATABRICKS_TOKEN=<token or secret>
```

The assistant is grounded by ranked source-backed cards and instructed not to invent events, prices, incidents, promotions, or official claims.
""")

st.caption("GoAround SG Databricks integration branch. Source-backed local discovery only. Verify deals, events and official updates at source before acting.")
