from __future__ import annotations

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

from src.goaround.agent import answer_with_databricks
from src.goaround.business import create_business_promo_card
from src.goaround.models import PickCard, UserContext
from src.goaround.ranking import haversine_m, infer_time_of_day, rank_cards
from src.goaround.seed_data import area_anchor_cards, source_registry_cards

load_dotenv()
st.set_page_config(page_title="GoAround SG", page_icon="📍", layout="wide")

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
LTA_BUS_STOPS_URL = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"
LTA_BUS_ARRIVAL_URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"

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


def api_headers() -> dict[str, str]:
    h = {"User-Agent": "goaround-sg-picks/0.1"}
    if os.getenv("DATA_GOV_API_KEY"):
        h["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return h


def lta_headers() -> dict[str, str]:
    return {"AccountKey": os.getenv("LTA_ACCOUNT_KEY", ""), "accept": "application/json"}


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in out.columns]
    return out.drop(columns=["_id"], errors="ignore")


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
        timeout=30,
    )
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
def poll_download_url(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=api_headers(), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


@st.cache_data(ttl=86400, show_spinner=False)
def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    try:
        gj = requests.get(poll_download_url(dataset_id), headers=api_headers(), timeout=90).json()
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
                "category": category,
                "name": str(name),
                "address": address,
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "source": "data.gov.sg",
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame(columns=["category", "name", "address", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=True)
def load_open_data_places() -> pd.DataFrame:
    frames = [
        load_geojson_points(DATASETS["hawker_centres"], "food"),
        load_geojson_points(DATASETS["supermarkets"], "grocery"),
        load_geojson_points(DATASETS["community_clubs"], "community"),
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["category", "name", "address", "lat", "lon", "source"])
    out = pd.concat(frames, ignore_index=True)
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["lat", "lon"]).drop_duplicates(["category", "name", "lat", "lon"])


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
    df["category"] = "transport"
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
        eta = (svc.get("NextBus") or {}).get("EstimatedArrival")
        mins = None
        if eta:
            try:
                eta_dt = datetime.fromisoformat(eta.replace("Z", "+00:00")).astimezone()
                mins = max(0, int((eta_dt - now).total_seconds() // 60))
            except Exception:
                mins = None
        rows.append({"service_no": svc.get("ServiceNo"), "operator": svc.get("Operator"), "next_min": mins})
    return pd.DataFrame(rows)


def nearest_df(df: pd.DataFrame, lat: float, lon: float, radius_m: int, limit: int = 10) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    out["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in out.itertuples()]
    return out[out.distance_m <= radius_m].sort_values("distance_m").head(limit)


def open_data_place_cards(places_near: pd.DataFrame) -> list[PickCard]:
    cards: list[PickCard] = []
    for row in places_near.head(30).itertuples():
        cat = str(row.category)
        card_type = "food" if cat == "food" else "deal" if cat == "grocery" else "event" if cat == "community" else "local_update"
        tags = {
            "food": ("food", "cheap food", "lunch", "dinner", "resident", "tourist"),
            "grocery": ("grocery", "shopping", "deal", "resident"),
            "community": ("community", "event", "family", "weekend", "resident"),
        }.get(cat, (cat,))
        cards.append(PickCard(
            id=f"open-{cat}-{abs(hash((row.name, row.lat, row.lon))) % 1000000}",
            card_type=card_type,
            category=cat,
            title=str(row.name),
            description=f"Nearby {cat.replace('_', ' ')} found from open data. Check details and opening hours before going.",
            source_name="data.gov.sg open data",
            source_url="https://data.gov.sg/",
            lat=float(row.lat),
            lon=float(row.lon),
            location_name=str(row.name),
            tags=tags,
            source_reliability=0.82,
            freshness_score=0.55,
        ))
    return cards


def bus_cards(bus_near: pd.DataFrame, arrivals: pd.DataFrame) -> list[PickCard]:
    if bus_near.empty:
        return []
    first = bus_near.iloc[0]
    desc = f"Nearest bus stop is {first['name']}."
    tags = ("transport", "commute", "resident", "worker/student")
    if not arrivals.empty and pd.notna(arrivals.iloc[0].get("next_min")):
        desc += f" Bus {arrivals.iloc[0]['service_no']} arrives in about {int(arrivals.iloc[0]['next_min'])} min."
        freshness = 0.95
    else:
        desc += " Open Transport section for live arrivals."
        freshness = 0.65
    return [PickCard(
        id=f"bus-{first['bus_stop_code']}",
        card_type="transport",
        category="transport",
        title="Transport now",
        description=desc,
        source_name="LTA DataMall",
        source_url="https://datamall.lta.gov.sg/",
        lat=float(first.lat),
        lon=float(first.lon),
        location_name=str(first["name"]),
        tags=tags,
        source_reliability=0.9,
        freshness_score=freshness,
    )]


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
        description="Use this to decide whether to choose indoor activities, mall options, or transport-friendly plans.",
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
        return "I do not have enough source-backed cards yet. Try widening your radius or checking Deals / Things To Do source links."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} {top.why_shown} Open the source before acting."


def render_pick_card(item) -> None:
    card = item.card
    distance = "" if item.distance_m is None else f" · {dist_label(item.distance_m)}"
    with st.container(border=True):
        st.markdown(f"### {icon_for(card.card_type)} {card.title}")
        st.caption(f"{card.category.title()}{distance} · score {item.score:.2f}")
        st.write(card.description)
        st.info(item.why_shown)
        cols = st.columns([1, 1, 1, 1.4])
        if cols[0].button("Save", key=f"save-{card.id}"):
            st.session_state.setdefault("saved_cards", []).append(card.id)
            st.success("Saved for this session.")
        if cols[1].button("Share", key=f"share-{card.id}"):
            st.code(f"{card.title}\n{card.description}\nSource: {card.source_url}")
        if cols[2].button("Remind", key=f"remind-{card.id}"):
            st.session_state.setdefault("reminders", []).append(card.id)
            st.success("Reminder saved for demo session.")
        cols[3].link_button("Open source", card.source_url)


def icon_for(card_type: str) -> str:
    return {
        "deal": "🔥",
        "food": "🍜",
        "event": "🎟",
        "transport": "🚌",
        "local_update": "🏘",
        "plan": "🧭",
    }.get(card_type, "📍")


# ----------------------------- App -----------------------------

st.title("📍 GoAround SG")
st.caption("AI-powered local lobang feed: useful deals, food, events, transport tips and local updates near where you live, work, study or visit.")

with st.sidebar:
    st.header("My area")
    mode = st.selectbox("I am here as", MODES)
    sample = st.selectbox("Try location", ["Custom", "308C Punggol Walk", "83 Punggol Central", "1 Cantonment Road", "1 Tanjong Pagar Plaza", "Chinatown MRT", "Orchard Road"])
    default_address = st.session_state.get("saved_area", "") if sample == "Custom" else sample
    address = st.text_input("Block / place / postal code", default_address)
    radius = st.slider("Discovery radius", 500, 3000, int(st.session_state.get("radius", 1500)), 100)
    interests = st.multiselect("Interests", INTERESTS, default=st.session_state.get("interests", ["cheap food", "grocery", "event", "deal"]))
    if st.button("Save my area"):
        st.session_state["saved_area"] = address
        st.session_state["radius"] = radius
        st.session_state["interests"] = interests
        st.success("Saved for this session. Lakebase can persist this in production.")

if not address:
    st.info("Enter a place, block or postal code to generate Today’s Picks.")
    st.stop()

try:
    profile = geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

with st.spinner("Building Today’s Picks from open data, live APIs and source-backed cards..."):
    places = load_open_data_places()
    near_places = nearest_df(places, profile["lat"], profile["lon"], radius, limit=30)
    bus_stops = load_bus_stops()
    bus_near = nearest_df(bus_stops, profile["lat"], profile["lon"], radius, limit=8) if not bus_stops.empty else pd.DataFrame()
    arrivals = get_bus_arrivals(str(bus_near.iloc[0].bus_stop_code)) if not bus_near.empty else pd.DataFrame()
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
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(open_data_place_cards(near_places))
cards.extend(bus_cards(bus_near, arrivals))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=16)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Matched area", profile.get("postal_code") or profile.get("road_name") or "n/a")
m2.metric("Today’s Picks", len(ranked))
m3.metric("Weather", weather.get("forecast") or "n/a")
m4.metric("Open-data places", len(near_places))

tab_today, tab_deals, tab_things, tab_ask, tab_myarea, tab_business, tab_data = st.tabs([
    "Today’s Picks", "Deals", "Things To Do", "Ask GoAround", "My Area", "Business Demo", "Data & Databricks"
])

with tab_today:
    st.subheader("Today’s Picks Near You")
    st.caption(f"{profile['address']} · {radius}m radius · {mode} mode · {context.time_of_day.title()} context")
    if not ranked:
        st.warning("No source-backed picks found. Try widening the radius or selecting more interests.")
    else:
        for item in ranked[:8]:
            render_pick_card(item)

with tab_deals:
    st.subheader("Deals and food lobang")
    deal_items = [x for x in ranked if x.card.card_type in {"deal", "food"}]
    if not deal_items:
        st.info("No deal/food cards found. Add a business promo or select cheap food/grocery interests.")
    for item in deal_items[:10]:
        render_pick_card(item)

with tab_things:
    st.subheader("Things To Do")
    thing_items = [x for x in ranked if x.card.card_type in {"event", "plan", "local_update"}]
    if not thing_items:
        st.info("No event/planning cards found. Try visitor mode or select family/weekend/tourist interests.")
    for item in thing_items[:10]:
        render_pick_card(item)

with tab_ask:
    st.subheader("Ask GoAround")
    st.caption("Ask for a source-aware local plan. Databricks Model Serving is used when configured.")
    examples = [
        "Plan a cheap lunch near me.",
        "What can I do with my kid this weekend?",
        "I am visiting this area for 2 hours. What should I do?",
        "What is useful around my block today?",
        "Any rainy-day options nearby?",
    ]
    st.write("Try:")
    for e in examples:
        st.markdown(f"- {e}")
    question = st.text_input("Your question")
    if question:
        st.markdown(answer_with_databricks(question, context, ranked, default_fallback_answer(ranked)))

with tab_myarea:
    st.subheader("My Area")
    st.write("This is the memory layer. The demo uses Streamlit session state; production should persist this in Lakebase.")
    st.json({
        "mode": mode,
        "address": profile["address"],
        "radius_m": radius,
        "interests": interests,
        "saved_cards": st.session_state.get("saved_cards", []),
        "reminders": st.session_state.get("reminders", []),
    })
    st.markdown("#### Nearby open-data anchors")
    if near_places.empty:
        st.info("No open-data places found in radius.")
    else:
        show = near_places.copy()
        show["distance"] = show["distance_m"].apply(dist_label)
        st.dataframe(show[["category", "name", "distance", "source"]].head(20), use_container_width=True, hide_index=True)
        fig = px.scatter_mapbox(show.head(30), lat="lat", lon="lon", color="category", hover_name="name", hover_data={"distance_m": ":.0f"}, zoom=13, height=430)
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

with tab_business:
    st.subheader("Business Promotion Demo")
    st.caption("Shows why businesses may use GoAround: hyperlocal promotion to users nearby with intent. Stored in session for demo; Lakebase in production.")
    with st.form("business_promo"):
        business_name = st.text_input("Business name", "Sample Cafe")
        promo_title = st.text_input("Promotion title", "Lunch set promo near you")
        promo_desc = st.text_area("Description", "Source-backed local promotion. Verify terms at source.")
        category = st.selectbox("Category", ["food", "grocery", "mall", "fitness", "family", "tourist", "service"])
        location_name = st.text_input("Location name", profile["address"])
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
                location_name=location_name,
                valid_until=str(valid_until),
                tags=tags,
            )
            st.session_state.setdefault("business_cards", []).append(card)
            st.success("Promotion created. It will appear in Today’s Picks if it ranks for this area.")
    if st.session_state.get("business_cards"):
        st.markdown("#### Session business cards")
        for c in st.session_state["business_cards"]:
            st.write(f"- {c.title} · {c.source_name} · {c.source_url}")

with tab_data:
    st.subheader("Open Data + AI Agent + Databricks")
    st.markdown("""
**This is not just API calls.** GoAround turns open data and source-backed feeds into a ranked local opportunity feed.

**Open data layer**
- data.gov.sg: hawker centres, supermarkets, community clubs and other public datasets
- OneMap: geocoding and location resolution
- LTA DataMall: bus stops and live bus arrivals when configured
- data.gov.sg weather APIs: weather context

**Databricks layer**
- Bronze: raw source data
- Silver: cleaned/geocoded local entities
- Gold: Today’s Picks, user-area profiles, interaction events, promotion/event cards
- Jobs: refresh open data and source-backed cards
- Model Serving: Ask GoAround and summary generation
- Genie: natural-language analytics over local demand and card performance
- Lakebase: saved areas, business submissions, reminders, interests and watchlists

**AI agent role**
- curate candidate cards
- rank by distance, freshness, interest, mode, time and weather
- explain why each card is shown
- answer questions without inventing unsourced claims
""")
    st.code("""Open data + live APIs + source registries
  -> Databricks Lakehouse
  -> Today’s Picks ranking engine
  -> AI agent / Ask GoAround
  -> Resident, visitor and business experiences""", language="text")

st.caption("GoAround SG prototype. Source-backed local discovery only. Verify deals, events, transport and official updates at source before acting.")
