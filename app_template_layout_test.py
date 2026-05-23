from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="GoAround SG Layout Test",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = ["GoAround Today", "Business Promotion", "What is GoAround?"]
FOOTER = "GoAroundSG — Team R4131N. Source-backed local discovery. Verify deals, events and official updates at source."

st.markdown(
    """
<style>
:root {
  color-scheme: light !important;
  --bg: #F7FAFC;
  --sidebar: #F4F7FB;
  --card: #FFFFFF;
  --text: #172B4D;
  --muted: #667085;
  --line: #E6EAF2;
  --blue: #0D6EFD;
  --green: #10B981;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="block-container"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  color-scheme: light !important;
}
[data-testid="stHeader"] {
  background: rgba(247,250,252,.98) !important;
}
.main .block-container {
  padding: 1.25rem 1rem 0.65rem 1rem !important;
  max-width: 1580px !important;
}
section[data-testid="stSidebar"] {
  background: var(--sidebar) !important;
  border-right: 1px solid #E5EAF3 !important;
}
section[data-testid="stSidebar"] .block-container {
  padding: 1rem .85rem .75rem .85rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
  gap: .55rem !important;
}
div[data-testid="stVerticalBlock"] {
  gap: .52rem !important;
}
.stMarkdown,.stCaption,.stRadio,.stSelectbox,.stTextInput,.stMultiSelect,.stSlider,.stTextArea,label,p,span,div,h1,h2,h3,h4,h5,h6,li {
  color: var(--text) !important;
}
.stCaption,.stCaption *,.muted {
  color: var(--muted) !important;
}
input,textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-baseweb="textarea"]>div {
  background: #FFFFFF !important;
  color: var(--text) !important;
  border-color: #D8DFEA !important;
  box-shadow: none !important;
}
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="popover"] div,[data-baseweb="menu"] div {
  background: #FFFFFF !important;
  color: var(--text) !important;
}
button[kind="primary"] {
  background: var(--blue) !important;
  color: #fff !important;
  border-radius: 12px !important;
  border: 0 !important;
}
button[kind="secondary"] {
  background: #FFFFFF !important;
  color: var(--text) !important;
  border: 1px solid #D8DFEA !important;
  border-radius: 12px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFFFF !important;
  border-color: var(--line) !important;
  border-radius: 22px !important;
  box-shadow: 0 10px 28px rgba(23,43,77,.055) !important;
}
.brand {
  display: flex;
  gap: .65rem;
  align-items: center;
  margin-bottom: .5rem;
}
.pin {
  width: 38px;
  height: 38px;
  border-radius: 50% 50% 50% 8px;
  background: linear-gradient(145deg,#0D6EFD,#20B2AA);
  transform: rotate(-45deg);
  position: relative;
  box-shadow: 0 8px 18px rgba(13,110,253,.18);
  flex: 0 0 auto;
}
.pin:after {
  content: "";
  width: 15px;
  height: 15px;
  background: #fff;
  border-radius: 50%;
  position: absolute;
  left: 11.5px;
  top: 11.5px;
}
.brand h1 {
  font-size: 19px;
  margin: 0;
  line-height: 1;
  color: #0D2B5C !important;
  font-weight: 850;
}
.brand h1 b { color: var(--green) !important; }
.brand p {
  font-size: 10.8px;
  margin: 3px 0 0 0;
  color: #596579 !important;
}
.weather-card {
  background: #F8FBFF;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: .65rem .72rem;
  box-shadow: 0 5px 16px rgba(23,43,77,.035);
}
.weather-card .temp {
  font-size: 1.15rem;
  font-weight: 850;
}
.weather-card .sub {
  font-size: .76rem;
  color: var(--muted) !important;
}
.statusbar {
  display: flex;
  gap: .36rem;
  flex-wrap: wrap;
  margin: 0 0 .75rem 0;
}
.chip {
  border-radius: 999px;
  padding: .25rem .56rem;
  font-size: .75rem;
  font-weight: 750;
  background: #EEF4FF;
  color: #175CD3 !important;
  border: 1px solid #D8E7FF;
}
.chip.warn {
  background: #FFF7E6;
  color: #B45309 !important;
  border-color: #FDE68A;
}
.card-title {
  font-size: 1.35rem;
  font-weight: 850;
  margin: 0;
}
.section-title {
  font-size: 1.02rem;
  font-weight: 850;
  margin: 0;
}
.placeholder {
  border: 1px dashed #C7D2E1;
  background: #F8FBFF;
  border-radius: 16px;
  padding: 1rem;
  color: #667085 !important;
  text-align: center;
}
.hero-placeholder {
  min-height: 190px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 1px dashed #C7D2E1;
  background: #F8FBFF;
  border-radius: 16px;
  color: #667085 !important;
}
.pick-placeholder {
  border: 1px solid #E6EAF2;
  border-radius: 18px;
  padding: .85rem;
  background: #FFFFFF;
  box-shadow: 0 5px 16px rgba(23,43,77,.035);
  min-height: 104px;
}
.kpi {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: .8rem;
  box-shadow: 0 5px 16px rgba(23,43,77,.035);
  min-height: 72px;
}
.kpi b {
  font-size: 1.3rem;
}
.business-gap { height: 1rem; }
.app-footer {
  margin-top: .8rem;
  padding: .55rem .75rem;
  border-top: 1px solid var(--line);
  color: var(--muted) !important;
  font-size: .78rem;
  text-align: center;
  line-height: 1.3;
}
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        "<div class='brand'><div class='pin'></div><div><h1>GoAround <b>SG</b></h1><p>AI local discovery assistant for Singapore</p></div></div>",
        unsafe_allow_html=True,
    )
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    with st.container(border=True):
        st.markdown("<div class='weather-card'><div style='display:flex;justify-content:space-between;align-items:center'><div><div class='temp'>Showers</div><div class='sub'>Sengkang</div></div><div style='font-size:1.75rem'>🌧️</div></div></div>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📍 My area</div>", unsafe_allow_html=True)
        st.selectbox("Try location", ["Auto / Current location", "Custom", "Sengkang", "Chinatown MRT"])
        st.button("◎ Detect current location", use_container_width=True)
        st.text_input("Block / place / postal code", "Sengkang")
        st.slider("Discovery radius", 500, 3000, 1500, 100)
        st.multiselect("Interests", ["cheap food", "grocery", "event", "deal", "family"], default=["cheap food", "grocery", "event", "deal"])
        st.button("💾 Save my area", type="primary", use_container_width=True)
        st.caption("🛡️ Source-backed. Verify details at source.")

st.markdown(
    "<div class='statusbar'><span class='chip warn'>Data: Source/API fallback</span><span class='chip warn'>AI: Safe fallback</span><span class='chip'>Area: Sengkang</span><span class='chip'>Weather: Showers</span></div>",
    unsafe_allow_html=True,
)

if page == "GoAround Today":
    chat_col, picks_col = st.columns([1.62, 1.10], gap="small")
    with chat_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>💬 Ask GoAround</h2>", unsafe_allow_html=True)
            st.caption("Conversation-style local assistant grounded by source-backed local picks.")
            st.markdown("<div class='hero-placeholder'>Chat message area placeholder<br>Should align visually with Today’s Picks</div>", unsafe_allow_html=True)
            q1, q2, q3, q4 = st.columns(4, gap="small")
            q1.button("🍴 Eat cheap", use_container_width=True)
            q2.button("📅 Weekend events", use_container_width=True)
            q3.button("🌧️ Rainy-day ideas", use_container_width=True)
            q4.button("🛒 Grocery deals", use_container_width=True)
            with st.form("layout_ask_form"):
                input_col, send_col = st.columns([9, 1], gap="small")
                input_col.text_input("Ask", placeholder="Ask GoAround about this area...", label_visibility="collapsed")
                send_col.form_submit_button("➤", use_container_width=True)
            st.markdown("<div class='placeholder'>Today’s local angle placeholder</div>", unsafe_allow_html=True)
    with picks_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>✨ Today’s Picks</h2>", unsafe_allow_html=True)
            st.caption("Curated picks near you, updated daily.")
            for i in range(4):
                st.markdown(f"<div class='pick-placeholder'><b>{i+1}. Pick card placeholder</b><br><span class='muted'>Description, distance and View details button.</span></div>", unsafe_allow_html=True)
            st.button("View more picks ›", use_container_width=True)

elif page == "Business Promotion":
    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, label, value in [(k1, "Active Promotions", "3"), (k2, "Clicks (7 days)", "128"), (k3, "Saves (7 days)", "47"), (k4, "Views (7 days)", "612")]:
        col.markdown(f"<div class='kpi'><span class='muted'>{label}</span><br><b>{value}</b></div>", unsafe_allow_html=True)
    st.markdown("<div class='business-gap'></div>", unsafe_allow_html=True)
    form_col, preview_col = st.columns([1.55, .85], gap="small")
    with form_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>Create Promotion</h2>", unsafe_allow_html=True)
            st.caption("Blank structure only. Form fields will be added after layout approval.")
            st.markdown("<div class='hero-placeholder'>Business form placeholder<br>Natural height, no clipping.</div>", unsafe_allow_html=True)
            st.markdown("<div class='placeholder'>Business value note placeholder</div>", unsafe_allow_html=True)
    with preview_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>Preview</h2>", unsafe_allow_html=True)
            st.caption("How promotion appears to users.")
            st.markdown("<div class='hero-placeholder'>Phone preview placeholder</div>", unsafe_allow_html=True)

else:
    with st.container(border=True):
        st.markdown("<h2 class='card-title'>What is GoAround SG?</h2>", unsafe_allow_html=True)
        st.markdown("<div class='hero-placeholder'>About content placeholder<br>Natural height, footer should stay below this container.</div>", unsafe_allow_html=True)

st.markdown(f"<div class='app-footer'>{FOOTER}</div>", unsafe_allow_html=True)
