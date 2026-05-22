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
st.set_page_config(page_title="GoAround SG", page_icon="📍", layout="wide", initial_sidebar_state="expanded")

ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
MODES = ["Resident", "Worker / Student", "Visitor", "Considering moving here"]
INTERESTS = ["cheap food", "grocery", "deal", "event", "family", "fitness", "shopping", "transport", "local update", "tourist", "rainy day", "coffee", "weekend"]
PAGES = ["GoAround Today", "Business Promotion", "What is GoAround?"]

st.markdown("""
<style>
:root{color-scheme:light!important;--bg:#F7FAFC;--card:#FFFFFF;--text:#172B4D;--muted:#667085;--line:#E6EAF2;--blue:#0D6EFD;--green:#10B981;}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stApp"],[data-testid="block-container"]{background:var(--bg)!important;color:var(--text)!important;color-scheme:light!important;}
[data-testid="stHeader"]{background:rgba(247,250,252,.98)!important;}
.main .block-container{padding:10px 18px 2px 18px!important;max-width:1580px!important;}
section[data-testid="stSidebar"]{background:#F4F7FB!important;color:var(--text)!important;border-right:1px solid #E5EAF3!important;}
section[data-testid="stSidebar"] .block-container{padding:12px 12px 6px 12px!important;}
div[data-testid="stVerticalBlock"]{gap:.36rem!important;}
/* light-mode hard overrides */
.stMarkdown,.stCaption,.stRadio,.stSelectbox,.stTextInput,.stMultiSelect,.stSlider,.stTextArea,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important;}
.stCaption,.stCaption *,.muted,.small{color:var(--muted)!important;}
input,textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-baseweb="textarea"]>div{background:#FFFFFF!important;color:#172B4D!important;border-color:#D8DFEA!important;box-shadow:none!important;}
input::placeholder,textarea::placeholder{color:#98A2B3!important;opacity:1!important;}
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="popover"] div,[data-baseweb="menu"] div{background:#FFFFFF!important;color:#172B4D!important;}
[data-baseweb="menu"]{background:#FFFFFF!important;border:1px solid #D8DFEA!important;}
[data-baseweb="tag"]{background:#EEF4FF!important;color:#175CD3!important;}
button[kind="primary"]{background:#0D6EFD!important;color:#fff!important;border-radius:12px!important;border:0!important;}
button[kind="secondary"]{background:#FFFFFF!important;color:#172B4D!important;border:1px solid #D8DFEA!important;border-radius:12px!important;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#FFFFFF!important;border-color:#E6EAF2!important;border-radius:22px!important;box-shadow:0 12px 34px rgba(23,43,77,.06)!important;color:#172B4D!important;}
.brand{display:flex;gap:10px;align-items:center;margin-bottom:10px;}.pin{width:40px;height:40px;border-radius:50% 50% 50% 8px;background:linear-gradient(145deg,#0D6EFD,#20B2AA);transform:rotate(-45deg);position:relative;box-shadow:0 8px 20px rgba(13,110,253,.18);flex:0 0 auto}.pin:after{content:"";width:16px;height:16px;background:#fff;border-radius:50%;position:absolute;left:12px;top:12px}.brand h1{font-size:21px;margin:0;line-height:1;color:#0D2B5C!important;font-weight:850}.brand h1 b{color:#10B981!important}.brand p{font-size:12px;margin:4px 0 0 0;color:#596579!important}.card-title{font-size:23px;font-weight:850;margin:0;color:#172B4D!important}.chat-row{display:flex;margin:10px 0}.chat-row.assistant{justify-content:flex-start}.chat-row.user{justify-content:flex-end}.chat-bubble{max-width:80%;border-radius:18px;padding:12px 14px;font-size:14px;line-height:1.45}.assistant .chat-bubble{background:#F1F5F9!important;color:#0F172A!important;border-bottom-left-radius:6px}.user .chat-bubble{background:#0D6EFD!important;color:#fff!important;border-bottom-right-radius:6px}.avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-right:10px;background:#EAF2FF;font-size:19px;flex:0 0 auto}.bot-hero{text-align:center;margin:10px 0}.bot-face{font-size:72px;line-height:1}.pick-card{border:1px solid #E6EAF2;border-radius:18px;padding:14px;margin-bottom:12px;background:#FFFFFF!important;box-shadow:0 5px 18px rgba(23,43,77,.04)}.pick-title{font-size:17px;font-weight:850;color:#172B4D!important;margin:0 0 4px}.pick-desc{font-size:13.5px;color:#344054!important;margin:0 0 10px}.rank{background:#0D6EFD;color:#fff!important;border-radius:8px;padding:3px 8px;font-weight:850;font-size:12px}.badge{display:inline-block;border-radius:999px;padding:4px 8px;font-size:12px;font-weight:750;background:#EEF4FF;color:#175CD3!important}.badge.green{background:#DFF8EE;color:#047857!important}.badge.purple{background:#F0E8FF;color:#6941C6!important}.badge.orange{background:#FFF2E0;color:#C05621!important}.visit{border:1px solid #E6EAF2;border-radius:12px;padding:7px 11px;color:#0D6EFD!important;font-weight:800;background:white;text-decoration:none}.footer-note{text-align:center;font-size:12px;color:#667085!important;margin-top:4px}.kpi{background:#fff;border:1px solid #E6EAF2;border-radius:18px;padding:14px;box-shadow:0 5px 18px rgba(23,43,77,.04)}.kpi b{font-size:25px;color:#172B4D!important}.phone{border:8px solid #EEF2F7;border-radius:36px;padding:14px;background:white;max-width:330px;margin:auto}.food-img{height:150px;border-radius:16px;background:linear-gradient(135deg,#FFE6C7,#F8B26A);display:flex;align-items:center;justify-content:center;font-size:72px;margin:8px 0}.primary{background:#0D6EFD;color:white!important;border-radius:12px;padding:12px 14px;text-align:center;font-weight:800;margin-top:8px}
</style>
""", unsafe_allow_html=True)

if "auto_location_attempted" not in st.session_state:
    st.session_state.auto_location_attempted = True
    st.session_state.request_browser_location = True


def esc(x: Any) -> str:
    return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md(x: str) -> str:
    return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", esc(x)).replace("\n", "<br>")


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=25)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    b = results[0]
    return {"address": b.get("ADDRESS") or query, "lat": float(b["LATITUDE"]), "lon": float(b["LONGITUDE"])}


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
    forecast = weather.get("forecast") or "Weather update"
    return [PickCard(id="weather-now", card_type="local_update", category="weather", title=f"Weather near {weather.get('area') or address}: {forecast}", description="Weather-aware context for indoor/outdoor planning.", source_name="data.gov.sg Weather API", source_url="https://data.gov.sg/", lat=lat, lon=lon, location_name=address, tags=("weather", "rainy day", "resident", "visitor"), source_reliability=.9, freshness_score=.95)]


def fallback_answer(ranked: list) -> str:
    if not ranked:
        return "I do not have enough source-backed cards yet. Try widening your radius."
    top = ranked[0]
    return f"Start with **{top.card.title}**. {top.card.description} Open the source before acting."


def render_chat(msg: dict[str, str]) -> None:
    role = msg.get("role", "assistant")
    avatar = "<div class='avatar'>🤖</div>" if role == "assistant" else ""
    st.markdown(f"<div class='chat-row {role}'>{avatar}<div class='chat-bubble'>{md(msg.get('content',''))}</div></div>", unsafe_allow_html=True)


def render_pick(item, idx: int) -> None:
    c = item.card
    category = c.category.upper().replace("LOCAL_UPDATE", "WEATHER")
    icon = "🌤️" if "weather" in c.category else "🍔" if "food" in c.category else "📅" if "event" in c.category else "✨"
    pill_class = "purple" if "weather" in c.category else "orange" if "food" in c.category else "green"
    st.markdown(f"""
<div class='pick-card'>
  <div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'><span class='rank'>{idx+1}</span><span class='badge {pill_class}'>{esc(category)}</span></div>
  <div style='float:right;font-size:42px;margin-left:8px'>{icon}</div>
  <div class='pick-title'>{esc(c.title)}</div>
  <div class='pick-desc'>{esc(c.description)}</div>
  <div style='display:flex;justify-content:space-between;align-items:center;font-size:12px;color:#667085'><span>📍 Within your area</span><a class='visit' href='{esc(c.source_url)}' target='_blank'>View details ↗</a></div>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("<div class='brand'><div class='pin'></div><div><h1>GoAround <b>SG</b></h1><p>AI local discovery assistant for Singapore</p></div></div>", unsafe_allow_html=True)
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    with st.container(border=True):
        st.markdown("### 📍 My area")
        st.caption("Tell us where you are to get better picks.")
        mode = st.selectbox("I am here as", MODES, index=0)
        sample = st.selectbox("Try location", ["Auto / Current location", "Custom", "Sengkang", "Chinatown MRT", "Orchard Road", "1 Tanjong Pagar Plaza"])
        if st.button("◎ Detect current location", use_container_width=True):
            st.session_state.request_browser_location = True
            st.rerun()
        if st.session_state.get("request_browser_location") and get_geolocation:
            loc = get_geolocation()
            coords = (loc or {}).get("coords") if isinstance(loc, dict) else None
            if coords:
                st.session_state.detected_profile = {"address": f"Current location ({coords['latitude']:.4f}, {coords['longitude']:.4f})", "lat": float(coords["latitude"]), "lon": float(coords["longitude"])}
                st.session_state.saved_area = st.session_state.detected_profile["address"]
                st.session_state.request_browser_location = False
        detected = st.session_state.get("detected_profile")
        default_address = detected["address"] if sample == "Auto / Current location" and detected else (st.session_state.get("saved_area", "Sengkang") if sample in ["Auto / Current location", "Custom"] else sample)
        address = st.text_input("Block / place / postal code", default_address)
        radius = st.slider("Discovery radius", 500, 3000, int(st.session_state.get("radius", 1500)), 100)
        interests = st.multiselect("Interests", INTERESTS, default=st.session_state.get("interests", ["cheap food", "grocery", "event", "deal"]))
        if st.button("💾 Save my area", type="primary", use_container_width=True):
            st.session_state.saved_area = address
            st.session_state.radius = radius
            st.session_state.interests = interests
            st.success("Saved for this session.")
    st.caption("🛡️ Source-backed local discovery. Verify final details at source.")

try:
    profile = st.session_state.get("detected_profile") if address == st.session_state.get("detected_profile", {}).get("address") else geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

weather = weather_near(profile["lat"], profile["lon"])
lakehouse_cards = load_gold_candidate_cards()
genai_mode = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN") and os.getenv("DATABRICKS_MODEL_ENDPOINT"))
context = UserContext(mode=mode, address=profile["address"], lat=profile["lat"], lon=profile["lon"], radius_m=radius, interests=tuple(interests), time_of_day=infer_time_of_day(), weather=weather.get("forecast"))

cards: list[PickCard] = []
cards.extend(lakehouse_cards)
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=12)

if page == "GoAround Today":
    chat_col, picks_col = st.columns([1.72, 1.08], gap="medium")
    with chat_col:
        with st.container(height=730, border=True):
            h1, h2 = st.columns([3, 1])
            h1.markdown("<h2 class='card-title'>💬 Ask GoAround</h2>", unsafe_allow_html=True)
            h2.caption("🛡️ Model Serving" if genai_mode else "🛡️ Safe fallback")
            st.caption("Conversation-style local assistant grounded by source-backed local picks.")
            if "ask_messages" not in st.session_state:
                st.session_state.ask_messages = [{"role": "assistant", "content": "Hi! I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visit plan."}]
            with st.container(height=300, border=False):
                for msg in st.session_state.ask_messages[-8:]:
                    render_chat(msg)
            if len(st.session_state.ask_messages) <= 1:
                st.markdown("<div class='bot-hero'><div class='bot-face'>🤖</div><h2>How can I help you today?</h2><p class='muted'>Try one of the ideas below or ask anything.</p></div>", unsafe_allow_html=True)
            pc = st.columns(4)
            for i, p in enumerate(["🍴 Eat cheap", "📅 Weekend events", "🌧️ Rainy-day ideas", "🛒 Grocery deals"]):
                if pc[i].button(p, key=f"quick-{i}", use_container_width=True):
                    st.session_state.pending_prompt = p
                    st.rerun()
            with st.form("ask_form", clear_on_submit=True):
                ic, sc = st.columns([9, 1])
                q = ic.text_input("Ask", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
                send = sc.form_submit_button("➤", use_container_width=True)
            st.markdown("<div class='footer-note'>GoAround can make mistakes. Please check details at the source.</div>", unsafe_allow_html=True)
            prompt = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
            if send and q.strip():
                prompt = q.strip()
            if prompt:
                st.session_state.ask_messages.append({"role": "user", "content": prompt})
                ans = answer_with_databricks(prompt, context, ranked, fallback_answer(ranked))
                st.session_state.ask_messages.append({"role": "assistant", "content": ans})
                st.rerun()
    with picks_col:
        with st.container(height=730, border=True):
            st.markdown("<h2 class='card-title'>✨ Today’s Picks</h2>", unsafe_allow_html=True)
            st.caption("Curated picks near you, updated daily.")
            with st.container(height=600, border=False):
                for idx, item in enumerate(ranked[:4]):
                    render_pick(item, idx)
            st.button("View more picks  ›", use_container_width=True)

elif page == "Business Promotion":
    k1, k2, k3, k4 = st.columns(4)
    for col, icon, label, value, change in [(k1,"🏷️","Active Promotions","3","▲ 1"),(k2,"🖱️","Clicks (7 days)","128","▲ 18%"),(k3,"🔖","Saves (7 days)","47","▲ 21%"),(k4,"👁️","Views (7 days)","612","▲ 12%")]:
        col.markdown(f"<div class='kpi'>{icon}<br><span class='muted'>{label}</span><br><b>{value}</b><br><span class='badge green'>{change}</span></div>", unsafe_allow_html=True)
    form_col, preview_col = st.columns([1.55, .85], gap="medium")
    with form_col:
        with st.container(height=635, border=True):
            st.subheader("Create Promotion")
            st.caption("Fill in the details to create your promotion. It will be reviewed before it goes live.")
            with st.form("business_promo"):
                c1, c2 = st.columns(2)
                business_name = c1.text_input("Business name", "Ah Boyz Chicken Rice")
                promo_title = c2.text_input("Promotion title *", "50% Off Signature Chicken Rice (Dinner Special)")
                c3, c4 = st.columns(2)
                category = c3.selectbox("Category *", ["Food & Dining", "Grocery", "Mall", "Family", "Fitness"])
                area = c4.text_input("Location / Area *", profile["address"][:45])
                c5, c6, c7 = st.columns(3)
                c5.date_input("Valid from")
                c6.date_input("Valid to")
                c7.text_input("Time", "5:00 PM – 9:00 PM")
                tags = st.multiselect("Audience / Interests", INTERESTS, default=["cheap food", "deal"])
                desc = st.text_area("Short description *", "Enjoy our signature Hainanese Chicken Rice at 50% off for dinner! Freshly steamed chicken, fragrant rice, and our homemade chilli.", height=90)
                source_url = st.text_input("CTA link", "https://example.com/promo")
                submitted = st.form_submit_button("✈️ Publish Promotion", type="primary")
            if submitted:
                card = create_business_promo_card(business_name, promo_title, desc, category, source_url, profile["lat"], profile["lon"], area, "", tags)
                st.session_state.setdefault("business_cards", []).append(card)
                st.success("Promotion created. It will appear in Today’s Picks after rerun if relevant.")
    with preview_col:
        with st.container(height=635, border=True):
            st.subheader("Preview")
            st.caption("This is how your promotion will appear.")
            st.markdown("<div class='phone'><div style='text-align:center;font-weight:850;color:#172B4D'>GoAround Today</div><span class='badge purple'>FOOD & DINING</span><span class='badge green'>50% OFF</span><div class='food-img'>🍚</div><h3>50% Off Signature Chicken Rice</h3><p class='muted'>Fresh chicken, fragrant rice and homemade chilli.</p><div class='primary'>View details ↗</div></div>", unsafe_allow_html=True)

else:
    with st.container(height=735, border=True):
        st.subheader("What is GoAround SG?")
        st.markdown("""
GoAround SG is a source-backed local discovery assistant for Singapore. It helps residents, workers, students, visitors, and businesses understand what is useful around a selected area.

### For residents and visitors
Ask questions such as:
- Where can I eat cheap near me?
- What can I do with my kid this weekend?
- What are rainy-day options nearby?
- Are there grocery deals or local updates around me?

### For businesses
Businesses can create local promotion cards that are shown to nearby users based on area, category, interests, and timing.

### Why it is different
GoAround SG combines open data, source registries, location, weather, ranking, and AI conversation into one daily local assistant.

### Databricks usage in this prototype
- **Databricks Apps** hosts the application.
- **Lakehouse / Delta** can store Bronze, Silver, and Gold local discovery data.
- **Databricks SQL Warehouse** serves Gold candidate cards when configured.
- **Model Serving / GenAI** powers Ask GoAround when a serving endpoint is configured.
- **Lakebase-ready workflows** support saved areas, reminders, and business promotions.
        """)

st.caption("GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.")
