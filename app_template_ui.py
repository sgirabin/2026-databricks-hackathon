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
WEATHER_2H_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"
MODES = ["Resident", "Worker / Student", "Visitor", "Considering moving here"]
INTERESTS = ["cheap food", "grocery", "deal", "event", "family", "fitness", "shopping", "transport", "local update", "tourist", "rainy day", "coffee", "weekend"]

st.markdown("""
<style>
:root{--blue:#0D6EFD;--navy:#172B4D;--green:#20B2AA;--line:#E6EAF2;--soft:#F7FAFF;--muted:#667085;}
.main .block-container{padding-top:1rem;max-width:1540px;padding-bottom:.5rem;}
section[data-testid="stSidebar"]{background:#F6F8FC;}
section[data-testid="stSidebar"] .block-container{padding:1rem .8rem .8rem .8rem;}
div[data-testid="stVerticalBlock"]{gap:.45rem;}
.brand{display:flex;gap:.65rem;align-items:center;margin-bottom:1rem;}
.logo-pin{width:42px;height:42px;border-radius:50% 50% 50% 8px;background:linear-gradient(145deg,#0D6EFD,#20B2AA);transform:rotate(-45deg);box-shadow:0 10px 24px rgba(13,110,253,.18);position:relative;}
.logo-pin:after{content:"";width:17px;height:17px;background:white;border-radius:50%;position:absolute;left:12px;top:12px;}
.brand-text h1{font-size:23px;margin:0;line-height:1.05;font-weight:850;color:#0D2B5C;letter-spacing:-.02em;}.brand-text h1 span{color:#10B981}.brand-text p{font-size:12px;margin:.25rem 0 0;color:#596579;}
.nav-item{display:flex;align-items:center;gap:.65rem;padding:.75rem .8rem;border-radius:14px;color:#253858;font-weight:700;font-size:15px;margin:.2rem 0;}.nav-active{background:#EAF2FF;color:#075FD1;box-shadow:inset 3px 0 0 #0D6EFD;}.nav-muted{color:#4B5563;}
.side-card{background:white;border:1px solid var(--line);border-radius:18px;padding:1rem;margin-top:1rem;box-shadow:0 4px 18px rgba(23,43,77,.04);}.side-card h3{font-size:18px;margin:0 0 .2rem;color:var(--navy)}.side-card p{font-size:12px;color:var(--muted);margin:.2rem 0 .8rem;}
.pill{display:inline-flex;align-items:center;gap:.35rem;border-radius:999px;padding:.35rem .65rem;font-size:12px;font-weight:750;margin:.15rem .25rem .15rem 0;background:#EEF4FF;color:#175CD3}.pill.green{background:#DFF8EE;color:#047857}.pill.purple{background:#F0E8FF;color:#6941C6}.pill.orange{background:#FFF2E0;color:#C05621}
.app-card{background:white;border:1px solid var(--line);border-radius:22px;box-shadow:0 12px 34px rgba(23,43,77,.06);}.hero-card{min-height:760px;padding:1.7rem 1.6rem 1.2rem;display:flex;flex-direction:column;}.card-title{font-size:23px;font-weight:850;color:var(--navy);letter-spacing:-.015em;margin:0;}.muted{color:var(--muted);font-size:13px}.top-toggle{display:inline-flex;background:#F2F4F8;padding:.25rem;border-radius:14px;border:1px solid var(--line);gap:.25rem;margin-bottom:1rem}.toggle-item{padding:.58rem 1.25rem;border-radius:11px;font-weight:800;color:#475467}.toggle-active{background:white;color:#0D6EFD;box-shadow:0 4px 12px rgba(23,43,77,.08)}
.chat-row{display:flex;margin:1rem 0}.chat-row.assistant{justify-content:flex-start}.chat-row.user{justify-content:flex-end}.chat-bubble{max-width:78%;border-radius:20px;padding:1rem 1.15rem;font-size:15px;line-height:1.5}.assistant .chat-bubble{background:#F1F5F9;color:#0F172A;border-bottom-left-radius:6px}.user .chat-bubble{background:#0D6EFD;color:white;border-bottom-right-radius:6px}.avatar{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-right:.75rem;background:#EAF2FF;font-size:22px;}
.bot-hero{text-align:center;margin:auto 0 1.5rem}.bot-face{font-size:120px;line-height:1;margin:1.25rem 0 .7rem}.bot-hero h2{font-size:24px;margin:.2rem 0;color:var(--navy)}.prompt-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin:1rem 0 1.35rem}.prompt{border:1px solid var(--line);border-radius:16px;padding:.8rem;background:#fff;font-weight:760;color:#253858;text-align:center;font-size:13px;min-height:58px;display:flex;align-items:center;justify-content:center}.input-wrap{border:1px solid var(--line);border-radius:999px;padding:.45rem;background:white;box-shadow:0 8px 22px rgba(23,43,77,.06)}.input-wrap div[data-testid="stForm"]{border:0;padding:0;margin:0}.send-btn button{border-radius:999px!important;background:#0D6EFD!important;color:#fff!important;min-height:42px!important}.input-wrap input{border:0!important;background:transparent!important;}
.picks-card{padding:1.55rem;min-height:760px}.pick{border:1px solid var(--line);border-radius:18px;padding:1.05rem;margin:.9rem 0;background:white;box-shadow:0 5px 18px rgba(23,43,77,.04)}.pick-head{display:flex;align-items:center;gap:.55rem;margin-bottom:.8rem}.rank{background:#0D6EFD;color:#fff;border-radius:8px;padding:.2rem .5rem;font-weight:850;font-size:12px}.pick-title{font-size:20px;font-weight:850;color:var(--navy);margin:.15rem 0}.pick-desc{font-size:14px;color:#344054;margin:.35rem 0 .8rem}.pick-footer{display:flex;justify-content:space-between;align-items:center;color:#667085;font-size:13px}.visit{border:1px solid var(--line);border-radius:12px;padding:.6rem .9rem;color:#0D6EFD;font-weight:800;background:white;text-decoration:none}.big-icon{float:right;font-size:54px;margin-left:.5rem}.business-kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:.9rem;margin-bottom:1.1rem}.kpi{background:white;border:1px solid var(--line);border-radius:18px;padding:1rem;box-shadow:0 5px 18px rgba(23,43,77,.04)}.kpi b{font-size:26px;color:var(--navy)}.form-card{padding:1.4rem}.phone-preview{padding:1.4rem;text-align:left}.phone{border:8px solid #EEF2F7;border-radius:36px;padding:1rem;background:white;max-width:330px;margin:auto}.food-img{height:145px;border-radius:16px;background:linear-gradient(135deg,#FFE6C7,#F8B26A);display:flex;align-items:center;justify-content:center;font-size:74px;margin:.8rem 0}.primary{background:#0D6EFD;color:white;border-radius:12px;padding:.75rem 1rem;text-align:center;font-weight:800;margin-top:.8rem}.footer-note{text-align:center;color:#667085;font-size:12px;margin-top:.75rem}
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
<div class='pick'>
  <div class='pick-head'><span class='rank'>{idx+1}</span><span class='pill {pill_class}'>{esc(category)}</span></div>
  <div class='big-icon'>{icon}</div>
  <div class='pick-title'>{esc(c.title)}</div>
  <div class='pick-desc'>{esc(c.description)}</div>
  <div class='pick-footer'><span>📍 Within your area</span><a class='visit' href='{esc(c.source_url)}' target='_blank'>View details ↗</a></div>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("""
<div class='brand'><div class='logo-pin'></div><div class='brand-text'><h1>GoAround <span>SG</span></h1><p>AI local discovery assistant for Singapore</p></div></div>
""", unsafe_allow_html=True)
    section = st.radio("Navigation", ["GoAround Today", "Business Promotion", "About Databricks"], label_visibility="collapsed")
    st.markdown("<div class='side-card'>", unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("🛡️ Source-backed local discovery. Verify final details at source.")

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
ranked = rank_cards(cards, context, limit=12)

if section == "GoAround Today":
    st.markdown("<div class='top-toggle'><span class='toggle-item toggle-active'>👤 User</span><span class='toggle-item'>🏪 Business</span></div>", unsafe_allow_html=True)
    chat_col, picks_col = st.columns([1.75, 1.1], gap="large")
    with chat_col:
        st.markdown("<div class='app-card hero-card'>", unsafe_allow_html=True)
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'><h2 class='card-title'>💬 Ask GoAround</h2><span class='muted'>🛡️ {'Model Serving' if genai_mode else 'Safe fallback'}</span></div>", unsafe_allow_html=True)
        if "ask_messages" not in st.session_state:
            st.session_state.ask_messages = [{"role":"assistant","content":"Hi! I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visit plan."}]
        with st.container(height=280, border=False):
            for msg in st.session_state.ask_messages[-5:]:
                render_chat(msg)
        if len(st.session_state.ask_messages) <= 1:
            st.markdown("<div class='bot-hero'><div class='bot-face'>🤖</div><h2>How can I help you today?</h2><p class='muted'>Try one of the ideas below or ask anything.</p></div>", unsafe_allow_html=True)
        prompts = ["🍴 Where can I eat cheap near me?", "📅 What’s happening this weekend?", "🌧️ Indoor activities for rainy days", "🛒 Show me grocery deals nearby"]
        cols = st.columns(4)
        for i, p in enumerate(prompts):
            if cols[i].button(p, key=f"quick-{i}", use_container_width=True):
                st.session_state.pending_prompt = p.split(" ",1)[1]
                st.rerun()
        st.markdown("<div class='input-wrap'>", unsafe_allow_html=True)
        with st.form("ask_form", clear_on_submit=True):
            ic, sc = st.columns([9,1])
            q = ic.text_input("Ask", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
            send = sc.form_submit_button("➤", use_container_width=True)
        st.markdown("</div><div class='footer-note'>GoAround can make mistakes. Please check details at the source.</div></div>", unsafe_allow_html=True)
        prompt = st.session_state.pop("pending_prompt", None) if "pending_prompt" in st.session_state else None
        if send and q.strip():
            prompt = q.strip()
        if prompt:
            st.session_state.ask_messages.append({"role":"user","content":prompt})
            ans = answer_with_databricks(prompt, context, ranked, fallback_answer(ranked))
            st.session_state.ask_messages.append({"role":"assistant","content":ans})
            st.rerun()
    with picks_col:
        st.markdown("<div class='app-card picks-card'><h2 class='card-title'>✨ Today’s Picks</h2><p class='muted'>Curated picks near you, updated daily.</p>", unsafe_allow_html=True)
        for idx, item in enumerate(ranked[:3]):
            render_pick(item, idx)
        st.button("View more picks  ›", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif section == "Business Promotion":
    st.markdown("<div class='top-toggle'><span class='toggle-item'>👤 User</span><span class='toggle-item toggle-active'>🏪 Business</span></div>", unsafe_allow_html=True)
    st.markdown("<div class='business-kpi'><div class='kpi'>🏷️<br><span class='muted'>Active Promotions</span><br><b>3</b><br><span class='pill green'>▲ 1 vs last 7 days</span></div><div class='kpi'>🖱️<br><span class='muted'>Clicks (7 days)</span><br><b>128</b><br><span class='pill green'>▲ 18%</span></div><div class='kpi'>🔖<br><span class='muted'>Saves (7 days)</span><br><b>47</b><br><span class='pill green'>▲ 21%</span></div><div class='kpi'>👁️<br><span class='muted'>Views (7 days)</span><br><b>612</b><br><span class='pill green'>▲ 12%</span></div></div>", unsafe_allow_html=True)
    form_col, preview_col = st.columns([1.55, .85], gap="large")
    with form_col:
        st.markdown("<div class='app-card form-card'>", unsafe_allow_html=True)
        st.subheader("Create Promotion")
        st.caption("Fill in the details to create your promotion. It will be reviewed before it goes live.")
        with st.form("business_promo"):
            c1,c2=st.columns(2)
            business_name=c1.text_input("Business name","Ah Boyz Chicken Rice")
            promo_title=c2.text_input("Promotion title *","50% Off Signature Chicken Rice (Dinner Special)")
            c3,c4=st.columns(2)
            category=c3.selectbox("Category *",["Food & Dining","Grocery","Mall","Family","Fitness"])
            area=c4.text_input("Location / Area *", profile["address"][:45])
            c5,c6,c7=st.columns(3)
            c5.date_input("Valid from")
            c6.date_input("Valid to")
            c7.text_input("Time", "5:00 PM – 9:00 PM")
            tags=st.multiselect("Audience / Interests", INTERESTS, default=["cheap food","deal"])
            desc=st.text_area("Short description *","Enjoy our signature Hainanese Chicken Rice at 50% off for dinner! Freshly steamed chicken, fragrant rice, and our homemade chilli.")
            source_url=st.text_input("CTA link", "https://example.com/promo")
            submitted=st.form_submit_button("✈️ Publish Promotion", type="primary")
        if submitted:
            card=create_business_promo_card(business_name,promo_title,desc,category,source_url,profile["lat"],profile["lon"],area,"",tags)
            st.session_state.setdefault("business_cards",[]).append(card)
            st.success("Promotion created. It will appear in Today’s Picks after rerun if relevant.")
        st.markdown("</div>", unsafe_allow_html=True)
    with preview_col:
        st.markdown("<div class='app-card phone-preview'><h2 class='card-title'>Preview</h2><p class='muted'>This is how your promotion will appear.</p><div class='phone'><div style='text-align:center;font-weight:850'>GoAround Today</div><span class='pill purple'>FOOD & DINING</span><span class='pill green'>50% OFF</span><div class='food-img'>🍚</div><h3>50% Off Signature Chicken Rice</h3><p class='muted'>Fresh chicken, fragrant rice and homemade chilli.</p><div class='primary'>View details ↗</div></div></div>", unsafe_allow_html=True)

else:
    st.markdown("<div class='app-card form-card'>", unsafe_allow_html=True)
    st.subheader("How GoAround SG uses Databricks")
    st.markdown("""
**Databricks Apps** runs the Streamlit experience on serverless app compute.  
**Lakehouse / Delta** stores open-data entities as Bronze, Silver and Gold tables.  
**Databricks SQL Warehouse** serves the Gold candidate cards to the app.  
**Model Serving / GenAI** powers Ask GoAround when a serving endpoint is available.  
**Lakebase-ready workflows** are represented by saved areas, reminders and business promotions.

```text
Open data + source registries -> Bronze Delta -> Silver entities -> Gold cards -> Ranking -> Ask GoAround
```
""")
    st.markdown("</div>", unsafe_allow_html=True)
