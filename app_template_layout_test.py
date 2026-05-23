from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="LAYOUT TEST - GoAround SG",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = ["Layout: GoAround Today", "Layout: Business Promotion", "Layout: What is GoAround?"]
FOOTER = "LAYOUT TEST ONLY — GoAroundSG / Team R4131N. No real data, no real chat, no production content."

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
  --test: #DC2626;
}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="block-container"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  color-scheme: light !important;
}
[data-testid="stHeader"] { background: rgba(247,250,252,.98) !important; }
.main .block-container { padding: 1.35rem 1rem .65rem 1rem !important; max-width: 1580px !important; }
section[data-testid="stSidebar"] { background: var(--sidebar) !important; border-right: 1px solid #E5EAF3 !important; }
section[data-testid="stSidebar"] .block-container { padding: 1rem .85rem .75rem .85rem !important; }
section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { gap: .55rem !important; }
div[data-testid="stVerticalBlock"] { gap: .52rem !important; }
.stMarkdown,.stCaption,.stRadio,.stSelectbox,.stTextInput,.stMultiSelect,.stSlider,.stTextArea,label,p,span,div,h1,h2,h3,h4,h5,h6,li { color: var(--text) !important; }
.stCaption,.stCaption *,.muted { color: var(--muted) !important; }
input,textarea,[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-baseweb="textarea"]>div { background: #FFFFFF !important; color: var(--text) !important; border-color: #D8DFEA !important; box-shadow: none !important; }
[data-baseweb="select"] span,[data-baseweb="select"] div,[data-baseweb="popover"] div,[data-baseweb="menu"] div { background: #FFFFFF !important; color: var(--text) !important; }
button[kind="primary"] { background: var(--blue) !important; color: #fff !important; border-radius: 12px !important; border: 0 !important; }
button[kind="secondary"] { background: #FFFFFF !important; color: var(--text) !important; border: 1px solid #D8DFEA !important; border-radius: 12px !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF !important; border-color: var(--line) !important; border-radius: 22px !important; box-shadow: 0 10px 28px rgba(23,43,77,.055) !important; }
.test-banner {
  border: 2px solid #FCA5A5;
  background: #FEF2F2;
  color: #991B1B !important;
  border-radius: 16px;
  padding: .75rem 1rem;
  font-weight: 900;
  text-align: center;
  margin-bottom: .8rem;
  letter-spacing: .02em;
}
.brand { display: flex; gap: .65rem; align-items: center; margin-bottom: .5rem; }
.pin { width: 38px; height: 38px; border-radius: 50% 50% 50% 8px; background: linear-gradient(145deg,#0D6EFD,#20B2AA); transform: rotate(-45deg); position: relative; box-shadow: 0 8px 18px rgba(13,110,253,.18); flex: 0 0 auto; }
.pin:after { content: ""; width: 15px; height: 15px; background: #fff; border-radius: 50%; position: absolute; left: 11.5px; top: 11.5px; }
.brand h1 { font-size: 19px; margin: 0; line-height: 1; color: #0D2B5C !important; font-weight: 850; }
.brand h1 b { color: var(--green) !important; }
.brand p { font-size: 10.8px; margin: 3px 0 0 0; color: #596579 !important; }
.statusbar { display: flex; gap: .36rem; flex-wrap: wrap; margin: 0 0 .75rem 0; }
.chip { border-radius: 999px; padding: .25rem .56rem; font-size: .75rem; font-weight: 750; background: #EEF4FF; color: #175CD3 !important; border: 1px solid #D8E7FF; }
.chip.test { background: #FEF2F2; color: #B91C1C !important; border-color: #FCA5A5; }
.card-title { font-size: 1.35rem; font-weight: 850; margin: 0; }
.section-title { font-size: 1.02rem; font-weight: 850; margin: 0; }
.placeholder { border: 2px dashed #93C5FD; background: #EFF6FF; border-radius: 16px; padding: 1rem; color: #1D4ED8 !important; text-align: center; font-weight: 800; }
.hero-placeholder { min-height: 220px; display: flex; align-items: center; justify-content: center; text-align: center; border: 2px dashed #93C5FD; background: #EFF6FF; border-radius: 16px; color: #1D4ED8 !important; font-weight: 800; }
.pick-placeholder { border: 2px dashed #93C5FD; border-radius: 18px; padding: .85rem; background: #EFF6FF; min-height: 104px; color:#1D4ED8!important; font-weight:800; }
.kpi { background: #EFF6FF; border: 2px dashed #93C5FD; border-radius: 16px; padding: .8rem; min-height: 72px; color:#1D4ED8!important; }
.kpi b { font-size: 1.3rem; }
.business-gap { height: 1rem; }
.app-footer { margin-top: .8rem; padding: .55rem .75rem; border-top: 1px solid var(--line); color: var(--muted) !important; font-size: .78rem; text-align: center; line-height: 1.3; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown("<div class='test-banner'>🧪 LAYOUT TEST VERSION — NOT THE REAL APP — PLACEHOLDERS ONLY</div>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        "<div class='brand'><div class='pin'></div><div><h1>Layout <b>Test</b></h1><p>Placeholder structure only</p></div></div>",
        unsafe_allow_html=True,
    )
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    with st.container(border=True):
        st.markdown("<div class='placeholder'>SIDEBAR WEATHER PLACEHOLDER</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📍 Sidebar controls placeholder</div>", unsafe_allow_html=True)
        st.selectbox("Try location", ["Placeholder A", "Placeholder B"])
        st.button("Placeholder action", use_container_width=True)
        st.text_input("Location input placeholder", "Placeholder location")
        st.slider("Radius placeholder", 500, 3000, 1500, 100)
        st.multiselect("Interests placeholder", ["A", "B", "C", "D"], default=["A", "B"])
        st.button("Save placeholder", type="primary", use_container_width=True)
        st.caption("Sidebar footer placeholder.")

st.markdown(
    "<div class='statusbar'><span class='chip test'>LAYOUT TEST</span><span class='chip'>Status chip</span><span class='chip'>Area chip</span><span class='chip'>Weather chip</span></div>",
    unsafe_allow_html=True,
)

if page == "Layout: GoAround Today":
    chat_col, picks_col = st.columns([1.62, 1.10], gap="small")
    with chat_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>LEFT MAIN PANEL PLACEHOLDER</h2>", unsafe_allow_html=True)
            st.caption("This will become Ask GoAround after layout approval.")
            st.markdown("<div class='hero-placeholder'>CHAT AREA PLACEHOLDER<br>Check height, width, spacing and alignment.</div>", unsafe_allow_html=True)
            q1, q2, q3, q4 = st.columns(4, gap="small")
            q1.button("Button 1", use_container_width=True)
            q2.button("Button 2", use_container_width=True)
            q3.button("Button 3", use_container_width=True)
            q4.button("Button 4", use_container_width=True)
            with st.form("layout_ask_form"):
                input_col, send_col = st.columns([9, 1], gap="small")
                input_col.text_input("Ask", placeholder="Input placeholder...", label_visibility="collapsed")
                send_col.form_submit_button("➤", use_container_width=True)
            st.markdown("<div class='placeholder'>LOWER NOTE PLACEHOLDER</div>", unsafe_allow_html=True)
    with picks_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>RIGHT RAIL PLACEHOLDER</h2>", unsafe_allow_html=True)
            st.caption("This will become Today’s Picks after layout approval.")
            for i in range(4):
                st.markdown(f"<div class='pick-placeholder'>{i+1}. RIGHT RAIL CARD PLACEHOLDER</div>", unsafe_allow_html=True)
            st.button("More placeholder ›", use_container_width=True)

elif page == "Layout: Business Promotion":
    k1, k2, k3, k4 = st.columns(4, gap="small")
    for col, label, value in [(k1, "KPI 1", "00"), (k2, "KPI 2", "00"), (k3, "KPI 3", "00"), (k4, "KPI 4", "00")]:
        col.markdown(f"<div class='kpi'>{label}<br><b>{value}</b></div>", unsafe_allow_html=True)
    st.markdown("<div class='business-gap'></div>", unsafe_allow_html=True)
    form_col, preview_col = st.columns([1.55, .85], gap="small")
    with form_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>BUSINESS FORM PANEL PLACEHOLDER</h2>", unsafe_allow_html=True)
            st.markdown("<div class='hero-placeholder'>FORM AREA PLACEHOLDER<br>Natural height, no clipping.</div>", unsafe_allow_html=True)
            st.markdown("<div class='placeholder'>BUSINESS NOTE PLACEHOLDER</div>", unsafe_allow_html=True)
    with preview_col:
        with st.container(border=True):
            st.markdown("<h2 class='card-title'>PREVIEW PANEL PLACEHOLDER</h2>", unsafe_allow_html=True)
            st.markdown("<div class='hero-placeholder'>PHONE PREVIEW PLACEHOLDER</div>", unsafe_allow_html=True)

else:
    with st.container(border=True):
        st.markdown("<h2 class='card-title'>ABOUT PAGE PLACEHOLDER</h2>", unsafe_allow_html=True)
        st.markdown("<div class='hero-placeholder'>ABOUT CONTENT PLACEHOLDER<br>Footer should stay below this container.</div>", unsafe_allow_html=True)

st.markdown(f"<div class='app-footer'>{FOOTER}</div>", unsafe_allow_html=True)
