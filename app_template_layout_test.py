from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="LAYOUT TARGET - GoAround SG",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
:root{color-scheme:light!important;--bg:#F7FAFC;--text:#172B4D;--muted:#667085;--line:#E6EAF2;--blue:#0D6EFD;--green:#10B981}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="block-container"]{background:var(--bg)!important;color:var(--text)!important;color-scheme:light!important;overflow:hidden!important}
[data-testid="stHeader"],section[data-testid="stSidebar"]{display:none!important}
.main .block-container{max-width:none!important;padding:.55rem .75rem .35rem .75rem!important}
div[data-testid="stHorizontalBlock"]{gap:.85rem!important}div[data-testid="stVerticalBlock"]{gap:.5rem!important}
div[data-testid="stVerticalBlockBorderWrapper"]{background:white!important;border-color:var(--line)!important;border-radius:22px!important;box-shadow:0 10px 28px rgba(23,43,77,.055)!important}
.stMarkdown,.stCaption,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important}.muted,.stCaption,.stCaption *{color:var(--muted)!important}
.brand{display:flex;gap:12px;align-items:center;margin-bottom:16px}.pin{width:40px;height:40px;border-radius:50%;background:linear-gradient(145deg,#0D6EFD,#20B2AA)}.brand-title{font-size:21px;font-weight:850;color:#0D2B5C}.green{color:var(--green)!important}.nav{border-top:1px solid var(--line);padding-top:14px;margin-top:8px}.nav div{border-radius:12px;padding:9px 10px;font-size:14px;font-weight:650}.active{background:#EEF4FF;color:#175CD3!important}.field{min-height:38px;border:1px solid #D8DFEA;border-radius:12px;background:white;display:flex;align-items:center;padding:0 12px;font-size:13px;color:#667085!important;margin-bottom:8px}.tag{border-radius:999px;padding:6px 10px;background:#EEF4FF;color:#175CD3!important;font-size:12px;font-weight:700;display:inline-block;margin:3px}.status{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:8px 13px;font-size:13px;margin-right:8px;background:white}.chatbox{height:calc(100vh - 310px);min-height:320px;border-radius:16px;background:#FBFCFE;border:1px dashed #D8E2F0;padding:18px;overflow:hidden}.bubble{border-radius:18px;background:#F1F5F9;padding:13px 16px;display:inline-block;margin:12px;max-width:65%;font-size:14px}.user{text-align:right}.quick{border:1px solid #D8DFEA;border-radius:12px;min-height:40px;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;background:white}.inputbar{min-height:54px;border:1px solid #D8DFEA;border-radius:16px;background:white;display:grid;grid-template-columns:44px 1fr 54px;align-items:center;margin-top:12px}.send{height:42px;width:42px;border-radius:12px;background:var(--blue);color:white!important;display:flex;align-items:center;justify-content:center}.picklist{height:calc(100vh - 172px);min-height:450px;overflow:hidden}.pick{min-height:120px;border:1px solid var(--line);border-radius:16px;padding:13px;background:white;margin-bottom:12px}.footer{text-align:center;color:var(--muted)!important;font-size:12px;margin-top:8px}
</style>
""", unsafe_allow_html=True)

left, right = st.columns([0.16, 0.84], gap="small")

with left:
    with st.container(height=760, border=True):
        st.markdown('<div class="brand"><div class="pin"></div><div><div class="brand-title">GoAround <span class="green">SG</span></div><div class="muted">AI local discovery assistant<br>for useful lobang near you.</div></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="nav"><div class="active">● GoAround Today</div><div>○ Business Promotion</div><div>○ About Databricks</div></div>', unsafe_allow_html=True)
        st.markdown('### My area')
        st.caption('Tell us where you are to get better picks.')
        st.markdown('<div class="field">Auto / Current location</div><div class="field">◎ Detect current location</div><div class="field">Seng Kang, Singapore<br>(1.3871, 103.8915)</div>', unsafe_allow_html=True)
        st.caption('Discovery radius: 1.5 km')
        st.markdown('<div class="field">────────●────────</div><span class="tag">cheap food ×</span><span class="tag">grocery ×</span><span class="tag">event ×</span><span class="tag">deal ×</span><div class="field" style="background:#0D6EFD;color:white!important;justify-content:center;font-weight:800;margin-top:10px">💾 Save my area</div>', unsafe_allow_html=True)
        st.caption('🛡️ Source-backed. Verify details at source.')

with right:
    with st.container(height=760, border=True):
        chat_col, picks_col = st.columns([0.69, 0.31], gap="large")
        with chat_col:
            st.markdown('# Ask GoAround')
            st.caption('Your conversation-style local assistant.')
            st.markdown('<span class="status">☀️ 35.0°C Sunny</span><span class="status">📍 Seng Kang, Singapore</span><span class="status">◎ Within 1.5 km</span>', unsafe_allow_html=True)
            st.markdown('<div class="chatbox"><div>🤖 <span class="bubble">Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan.</span></div><div class="user"><span class="bubble">Any cheap food spots near me?</span> 👤</div><div>🤖 <span class="bubble">Here are some budget-friendly options near you within 1.5 km.</span></div></div>', unsafe_allow_html=True)
            q1,q2,q3,q4 = st.columns(4, gap="small")
            for col,label in zip([q1,q2,q3,q4], ['🍴 Eat cheap','📅 Weekend events','🌧️ Rainy-day ideas','🛒 Grocery deals']):
                col.markdown(f'<div class="quick">{label}</div>', unsafe_allow_html=True)
            st.markdown('<div class="inputbar"><div style="text-align:center">📎</div><div class="muted">Ask GoAround about this area...</div><div class="send">➤</div></div><div class="footer">GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.</div>', unsafe_allow_html=True)
        with picks_col:
            st.markdown('## Today’s Picks')
            st.caption('Curated for you based on your area and interests.')
            st.markdown('<div class="picklist"><div class="pick"><b>🤖 $3.50 Chicken Rice Stall</b><br><span class="muted">Food · Google Maps · 0.4 km</span><br>Popular hawker stall with good reviews.</div><div class="pick"><b>🎉 Community Flea Market</b><br><span class="muted">Eventbrite · 0.6 km</span><br>Local market with pre-loved deals.</div><div class="pick"><b>🏷️ NTUC FairPrice Deals</b><br><span class="muted">FairPrice · 0.5 km</span><br>Weekly grocery offers near Sengkang.</div></div><div class="footer">More picks⌄</div>', unsafe_allow_html=True)
