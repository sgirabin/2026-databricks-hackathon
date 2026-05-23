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
INTERESTS = [
    "cheap food", "grocery", "deal", "event", "family", "fitness", "shopping",
    "transport", "local update", "tourist", "rainy day", "coffee", "weekend",
]
PAGES = ["GoAround Today", "Business Promotion", "What is GoAround?"]
FOOTER = "GoAroundSG — Team R4131N. Source-backed local discovery. Verify deals, events and official updates at source."
PANEL_HEIGHT = 640
SIDEBAR_PANEL_HEIGHT = 595
BUSINESS_PANEL_HEIGHT = 525
ABOUT_PANEL_HEIGHT = 610

st.markdown(
    """
<style>
:root{color-scheme:light!important;--bg:#F7FAFC;--card:#FFFFFF;--text:#172B4D;--muted:#667085;--line:#E6EAF2;--blue:#0D6EFD;--green:#10B981;}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="block-container"]{background:var(--bg)!important;color:var(--text)!important;color-scheme:light!important;}
[data-testid="stHeader"]{background:rgba(247,250,252,.98)!important;}
.main .block-container{padding:2rem 1rem .8rem 1rem!important;max-width:1580px!important;}
section[data-testid="stSidebar"]{background:#F4F7FB!important;color:var(--text)!important;border-right:1px solid #E5EAF3!important;}
section[data-testid="stSidebar"] .block-container{padding:1rem .85rem .8rem .85rem!important;}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]{gap:.5rem!important;}
div[data-testid="stVerticalBlock"]{gap:.48rem!important;}
.stMarkdown,.stCaption,.stRadio,.stSelectbox,.stTextInput,.stMultiSelect,.stSlider,.stTextArea,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important;}
.stCaption,.stCaption *,.muted,.small{color:var(--muted)!important;}
input,textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-baseweb="textarea"]>div{background:#FFFFFF!important;color:#172B4D!important;border-color:#D8DFEA!important;box-shadow:none!important;}
input::placeholder,textarea::placeholder{color:#98A2B3!important;opacity:1!important;}
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="popover"] div,[data-baseweb="menu"] div{background:#FFFFFF!important;color:#172B4D!important;}
[data-baseweb="menu"]{background:#FFFFFF!important;border:1px solid #D8DFEA!important;}
[data-baseweb="tag"]{background:#EEF4FF!important;color:#175CD3!important;min-height:1.42rem!important;font-size:.8rem!important;}
button[kind="primary"]{background:#0D6EFD!important;color:#fff!important;border-radius:12px!important;border:0!important;}
button[kind="secondary"]{background:#FFFFFF!important;color:#172B4D!important;border:1px solid #D8DFEA!important;border-radius:12px!important;}
section[data-testid="stSidebar"] button{min-height:2.25rem!important;padding:.25rem .7rem!important;}
section[data-testid="stSidebar"] label{font-size:.84rem!important;margin-bottom:.08rem!important;}
section[data-testid="stSidebar"] [data-baseweb="select"]>div{min-height:2.2rem!important;}
section[data-testid="stSidebar"] input{min-height:2.08rem!important;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#FFFFFF!important;border-color:#E6EAF2!important;border-radius:22px!important;box-shadow:0 10px 28px rgba(23,43,77,.055)!important;color:#172B4D!important;}
.brand{display:flex;gap:.65rem;align-items:center;margin-bottom:.65rem;}.pin{width:38px;height:38px;border-radius:50% 50% 50% 8px;background:linear-gradient(145deg,#0D6EFD,#20B2AA);transform:rotate(-45deg);position:relative;box-shadow:0 8px 18px rgba(13,110,253,.18);flex:0 0 auto}.pin:after{content:"";width:15px;height:15px;background:#fff;border-radius:50%;position:absolute;left:11.5px;top:11.5px}.brand h1{font-size:19px;margin:0;line-height:1;color:#0D2B5C!important;font-weight:850}.brand h1 b{color:#10B981!important}.brand p{font-size:10.8px;margin:3px 0 0 0;color:#596579!important}.weather-card{background:#F8FBFF;border:1px solid #E6EAF2;border-radius:16px;padding:.6rem .7rem;margin:.15rem 0 .55rem;box-shadow:0 5px 16px rgba(23,43,77,.035)}.weather-card .temp{font-size:1.2rem;font-weight:850;color:#172B4D!important}.weather-card .sub{font-size:.76rem;color:#667085!important}.statusbar{display:flex;gap:.34rem;flex-wrap:wrap;margin:.05rem 0 .75rem}.chip{border-radius:999px;padding:.25rem .55rem;font-size:.74rem;font-weight:750;background:#EEF4FF;color:#175CD3!important;border:1px solid #D8E7FF}.chip.green{background:#DFF8EE;color:#047857!important;border-color:#BBF7D0}.chip.warn{background:#FFF7E6;color:#B45309!important;border-color:#FDE68A}.card-title{font-size:1.38rem;font-weight:850;margin:0;color:#172B4D!important}.section-title{font-size:1.03rem;font-weight:850;margin:0;color:#172B4D!important}.chat-row{display:flex;margin:.65rem 0}.chat-row.assistant{justify-content:flex-start}.chat-row.user{justify-content:flex-end}.chat-bubble{max-width:82%;border-radius:18px;padding:.72rem .9rem;font-size:.91rem;line-height:1.45}.assistant .chat-bubble{background:#F1F5F9!important;color:#0F172A!important;border-bottom-left-radius:6px}.user .chat-bubble{background:#0D6EFD!important;color:#fff!important;border-bottom-right-radius:6px}.avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-right:.55rem;background:#EAF2FF;font-size:1rem;flex:0 0 auto}.quick-title{font-weight:850;text-align:center;font-size:1.18rem;margin:.5rem 0 .08rem}.quick-sub{text-align:center;font-size:.82rem;color:#667085!important;margin:0 0 .38rem}.bot-mini{text-align:center;font-size:2.45rem;line-height:1;margin:.35rem 0 .05rem}.pick-card{border:1px solid #E6EAF2;border-radius:18px;padding:.78rem;margin-bottom:.5rem;background:#FFFFFF!important;box-shadow:0 5px 16px rgba(23,43,77,.035)}.pick-title{font-size:.96rem;font-weight:850;color:#172B4D!important;margin:0 0 .15rem}.pick-desc{font-size:.81rem;color:#344054!important;margin:0 0 .42rem}.rank{background:#0D6EFD;color:#fff!important;border-radius:8px;padding:.11rem .4rem;font-weight:850;font-size:.72rem}.badge{display:inline-block;border-radius:999px;padding:.18rem .44rem;font-size:.69rem;font-weight:750;background:#EEF4FF;color:#175CD3!important}.badge.green{background:#DFF8EE;color:#047857!important}.badge.purple{background:#F0E8FF;color:#6941C6!important}.badge.orange{background:#FFF2E0;color:#C05621!important}.visit{border:1px solid #E6EAF2;border-radius:12px;padding:.34rem .6rem;color:#0D6EFD!important;font-weight:800;background:white;text-decoration:none}.kpi{background:#fff;border:1px solid #E6EAF2;border-radius:16px;padding:.78rem;box-shadow:0 5px 16px rgba(23,43,77,.035)}.kpi b{font-size:1.28rem;color:#172B4D!important}.phone{border:7px solid #EEF2F7;border-radius:32px;padding:.75rem;background:white;max-width:300px;margin:auto}.food-img{height:105px;border-radius:16px;background:linear-gradient(135deg,#FFE6C7,#F8B26A);display:flex;align-items:center;justify-content:center;font-size:3rem;margin:.38rem 0}.primary{background:#0D6EFD;color:white!important;border-radius:12px;padding:.56rem .75rem;text-align:center;font-weight:800;margin-top:.38rem}.footer-note{text-align:center;font-size:.72rem;color:#667085!important;margin-top:.2rem}.compact-footer{font-size:.74rem;color:#667085!important;line-height:1.25;margin-top:.45rem;}.insight-box{background:#F8FBFF;border:1px solid #E6EAF2;border-radius:14px;padding:.68rem;margin-top:.8rem;font-size:.84rem;color:#344054!important}.business-gap{height:1.15rem}.app-footer{margin-top:.75rem;padding:.55rem .75rem;border-top:1px solid #E6EAF2;color:#667085!important;font-size:.78rem;text-align:center;line-height:1.3;background:transparent}.form-soft-note{background:#F8FBFF;border:1px solid #E6EAF2;border-radius:14px;padding:.62rem;margin-top:.5rem;font-size:.83rem;color:#344054!important}
@media (max-height:760px){.main .block-container{padding-top:1.25rem!important}.bot-mini{font-size:2.05rem}.quick-title{font-size:1.05rem}.pick-card{padding:.66rem;margin-bottom:.42rem}.chat-row{margin:.48rem 0}.business-gap{height:.85rem}.app-footer{font-size:.72rem;padding:.42rem .65rem}.statusbar{margin-bottom:.5rem}}
</style>
""",
    unsafe_allow_html=True,
)

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


def weather_icon(forecast: str | None) -> str:
    f = (forecast or "").lower()
    if "thunder" in f:
        return "⛈️"
    if "rain" in f or "showers" in f:
        return "🌧️"
    if "cloud" in f:
        return "⛅"
    if "fair" in f or "sun" in f:
        return "☀️"
    return "🌤️"


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
  <div style='display:flex;align-items:center;gap:8px;margin-bottom:5px'><span class='rank'>{idx+1}</span><span class='badge {pill_class}'>{esc(category)}</span></div>
  <div style='float:right;font-size:1.9rem;margin-left:8px'>{icon}</div>
  <div class='pick-title'>{esc(c.title)}</div>
  <div class='pick-desc'>{esc(c.description)}</div>
  <div style='display:flex;justify-content:space-between;align-items:center;font-size:.72rem;color:#667085'><span>📍 Within your area</span><a class='visit' href='{esc(c.source_url)}' target='_blank'>View details ↗</a></div>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("<div class='brand'><div class='pin'></div><div><h1>GoAround <b>SG</b></h1><p>AI local discovery assistant for Singapore</p></div></div>", unsafe_allow_html=True)
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    with st.container(height=SIDEBAR_PANEL_HEIGHT, border=True):
        weather_slot = st.empty()
        st.markdown("<div class='section-title'>📍 My area</div>", unsafe_allow_html=True)
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
            st.success("Saved.")
        st.markdown("<div class='compact-footer'>🛡️ Source-backed. Verify details at source.</div>", unsafe_allow_html=True)

try:
    profile = st.session_state.get("detected_profile") if address == st.session_state.get("detected_profile", {}).get("address") else geocode(address)
except Exception as exc:
    st.error(f"Could not find this location with OneMap: {exc}")
    st.stop()

weather = weather_near(profile["lat"], profile["lon"])
weather_slot.markdown(
    f"<div class='weather-card'><div style='display:flex;justify-content:space-between;align-items:center'><div><div class='temp'>{esc(weather.get('forecast') or 'Weather')}</div><div class='sub'>{esc(weather.get('area') or profile['address'][:28])}</div></div><div style='font-size:1.75rem'>{weather_icon(weather.get('forecast'))}</div></div></div>",
    unsafe_allow_html=True,
)

lakehouse_cards = load_gold_candidate_cards()
lakehouse_mode = bool(lakehouse_cards)
genai_mode = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN") and os.getenv("DATABRICKS_MODEL_ENDPOINT"))
mode = "Resident"
context = UserContext(mode=mode, address=profile["address"], lat=profile["lat"], lon=profile["lon"], radius_m=radius, interests=tuple(interests), time_of_day=infer_time_of_day(), weather=weather.get("forecast"))

cards: list[PickCard] = []
cards.extend(lakehouse_cards)
cards.extend(source_registry_cards())
cards.extend(area_anchor_cards(profile["address"], profile["lat"], profile["lon"]))
cards.extend(weather_cards(weather, profile["lat"], profile["lon"], profile["address"]))
cards.extend(st.session_state.get("business_cards", []))
ranked = rank_cards(cards, context, limit=12)

data_text = "Lakehouse" if lakehouse_mode else "Source/API fallback"
ai_text = "Model Serving" if genai_mode else "Safe fallback"
st.markdown(
    f"<div class='statusbar'><span class='chip {'green' if lakehouse_mode else 'warn'}'>Data: {esc(data_text)}</span><span class='chip {'green' if genai_mode else 'warn'}'>AI: {esc(ai_text)}</span><span class='chip'>Area: {esc(profile['address'][:72])}</span><span class='chip'>Weather: {esc(weather.get('forecast') or 'n/a')}</span></div>",
    unsafe_allow_html=True,
)

if page == "GoAround Today":
    chat_col, picks_col = st.columns([1.62, 1.10], gap="small")
    with chat_col:
        with st.container(height=PANEL_HEIGHT, border=True):
            h1, h2 = st.columns([3, 1], gap="small")
            h1.markdown("<h2 class='card-title'>💬 Ask GoAround</h2>", unsafe_allow_html=True)
            h2.caption("🛡️ Model Serving" if genai_mode else "🛡️ Safe fallback")
            if "ask_messages" not in st.session_state:
                st.session_state.ask_messages = [{"role": "assistant", "content": "Hi! I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visit plan."}]
            for msg in st.session_state.ask_messages[-4:]:
                render_chat(msg)
            st.markdown("<div class='bot-mini'>🤖</div><div class='quick-title'>How can I help you today?</div><div class='quick-sub'>Ask naturally, or start with one of these.</div>", unsafe_allow_html=True)
            pc = st.columns(4, gap="small")
            for i, p in enumerate(["🍴 Eat cheap", "📅 Weekend events", "🌧️ Rainy-day ideas", "🛒 Grocery deals"]):
                if pc[i].button(p, key=f"quick-{i}", use_container_width=True):
                    st.session_state.pending_prompt = p
                    st.rerun()
            with st.form("ask_form", clear_on_submit=True):
                ic, sc = st.columns([9, 1], gap="small")
                q = ic.text_input("Ask", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
                send = sc.form_submit_button("➤", use_container_width=True)
            st.markdown("<div class='footer-note'>GoAround can make mistakes. Please check details at the source.</div>", unsafe_allow_html=True)
            if ranked:
                st.markdown(
                    f"<div class='insight-box'><b>Today’s local angle:</b> {esc(ranked[0].card.title)} is the top source-backed pick for this area. Ask GoAround to turn these picks into a lunch plan, family plan, rainy-day plan, or short visitor itinerary.</div>",
                    unsafe_allow_html=True,
                )
            prompt = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
            if send and q.strip():
                prompt = q.strip()
            if prompt:
                st.session_state.ask_messages.append({"role": "user", "content": prompt})
                ans = answer_with_databricks(prompt, context, ranked, fallback_answer(ranked))
                st.session_state.ask_messages.append({"role": "assistant", "content": ans})
                st.rerun()
    with picks_col:
        with st.container(height=PANEL_HEIGHT, border=True):
            st.markdown("<h2 class='card-title'>✨ Today’s Picks</h2>", unsafe_allow_html=True)
            st.caption("Curated picks near you, updated daily.")
            for idx, item in enumerate(ranked[:5]):
                render_pick(item, idx)
            if len(ranked) > 5:
                with st.expander("View more picks"):
                    for idx, item in enumerate(ranked[5:10], start=5):
                        render_pick(item, idx)

elif page == "Business Promotion":
    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, icon, label, value, change in [(k1, "🏷️", "Active Promotions", "3", "▲ 1"), (k2, "🖱️", "Clicks (7 days)", "128", "▲ 18%"), (k3, "🔖", "Saves (7 days)", "47", "▲ 21%"), (k4, "👁️", "Views (7 days)", "612", "▲ 12%")]:
        col.markdown(f"<div class='kpi'>{icon}<br><span class='muted'>{label}</span><br><b>{value}</b><br><span class='badge green'>{change}</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='business-gap'></div>", unsafe_allow_html=True)
    form_col, preview_col = st.columns([1.55, .85], gap="small")
    with form_col:
        with st.container(height=BUSINESS_PANEL_HEIGHT, border=True):
            st.subheader("Create Promotion")
            st.caption("Create a location-aware promotion that can appear in Today’s Picks when relevant.")
            with st.form("business_promo"):
                c1, c2 = st.columns(2, gap="small")
                business_name = c1.text_input("Business name", "Ah Boyz Chicken Rice")
                promo_title = c2.text_input("Promotion title *", "50% Off Signature Chicken Rice (Dinner Special)")
                c3, c4 = st.columns(2, gap="small")
                category = c3.selectbox("Category *", ["Food & Dining", "Grocery", "Mall", "Family", "Fitness"])
                area = c4.text_input("Location / Area *", profile["address"][:45])
                c5, c6, c7 = st.columns(3, gap="small")
                c5.date_input("Valid from")
                c6.date_input("Valid to")
                c7.text_input("Time", "5:00 PM – 9:00 PM")
                tags = st.multiselect("Audience / Interests", INTERESTS, default=["cheap food", "deal"])
                desc = st.text_area("Short description *", "Enjoy our signature Hainanese Chicken Rice at 50% off for dinner! Freshly steamed chicken, fragrant rice, and our homemade chilli.", height=72)
                source_url = st.text_input("CTA link", "https://example.com/promo")
                submitted = st.form_submit_button("✈️ Publish Promotion", type="primary")
            if submitted:
                card = create_business_promo_card(business_name, promo_title, desc, category, source_url, profile["lat"], profile["lon"], area, "", tags)
                st.session_state.setdefault("business_cards", []).append(card)
                st.success("Promotion created. It will appear in Today’s Picks after rerun if relevant.")
            st.markdown("<div class='form-soft-note'><b>Business value:</b> promotions are ranked by location, interest, freshness, and source trust — so businesses can reach nearby users when they are actively asking what to eat, buy, or do.</div>", unsafe_allow_html=True)
    with preview_col:
        with st.container(height=BUSINESS_PANEL_HEIGHT, border=True):
            st.subheader("Preview")
            st.caption("How your promotion appears to nearby users.")
            st.markdown("<div class='phone'><div style='text-align:center;font-weight:850;color:#172B4D'>GoAround Today</div><span class='badge purple'>FOOD & DINING</span><span class='badge green'>50% OFF</span><div class='food-img'>🍚</div><h3>50% Off Signature Chicken Rice</h3><p class='muted'>Fresh chicken, fragrant rice and homemade chilli.</p><div class='primary'>View details ↗</div></div>", unsafe_allow_html=True)

else:
    with st.container(height=ABOUT_PANEL_HEIGHT, border=True):
        st.subheader("What is GoAround SG?")
        st.markdown("""
GoAround SG is a source-backed local discovery assistant for Singapore. It helps people understand what is useful around a selected area.

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

st.markdown(f"<div class='app-footer'>{FOOTER}</div>", unsafe_allow_html=True)
