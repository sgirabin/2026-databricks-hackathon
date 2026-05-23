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
:root{color-scheme:light!important;--bg:#F7FAFC;--text:#172B4D;--muted:#667085;--line:#E6EAF2;--blue:#0D6EFD;--green:#10B981;--soft:#F6F9FC}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="block-container"]{background:var(--bg)!important;color:var(--text)!important;color-scheme:light!important;overflow:hidden!important}
[data-testid="stHeader"],section[data-testid="stSidebar"]{display:none!important}
.main .block-container{max-width:none!important;padding:.45rem .65rem .25rem .65rem!important}
div[data-testid="stHorizontalBlock"]{gap:.9rem!important}div[data-testid="stVerticalBlock"]{gap:.45rem!important}
div[data-testid="stVerticalBlockBorderWrapper"]{background:white!important;border-color:var(--line)!important;border-radius:20px!important;box-shadow:0 10px 28px rgba(23,43,77,.06)!important;overflow:hidden!important}
.stMarkdown,.stCaption,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important}.muted,.stCaption,.stCaption *{color:var(--muted)!important}
.brand{display:flex;gap:12px;align-items:center;margin-bottom:18px}.pin{width:38px;height:38px;border-radius:50%;background:linear-gradient(145deg,#0D6EFD,#20B2AA);box-shadow:0 8px 18px rgba(13,110,253,.18);flex:0 0 auto}.brand-title{font-size:19px;font-weight:850;color:#0D2B5C}.green{color:var(--green)!important}.subtitle{font-size:12px;line-height:1.45;color:var(--muted)!important;margin-top:3px}.nav{border-top:1px solid var(--line);padding-top:13px;margin-top:8px}.nav div{border-radius:12px;padding:9px 10px;font-size:13px;font-weight:700;margin-bottom:4px}.active{background:#EEF4FF;color:#175CD3!important}.side-title{font-size:19px;font-weight:850;margin:14px 0 4px 0}.field{min-height:38px;border:1px solid #D8DFEA;border-radius:12px;background:white;display:flex;align-items:center;padding:0 12px;font-size:12.5px;color:#667085!important;margin-bottom:8px}.tag{border-radius:999px;padding:5px 9px;background:#EEF4FF;color:#175CD3!important;font-size:11.5px;font-weight:700;display:inline-block;margin:3px}.status{display:inline-block;border:1px solid var(--line);border-radius:10px;padding:8px 13px;font-size:12.5px;margin:0 8px 10px 0;background:white}.chatbox{height:calc(100vh - 318px);min-height:300px;border-radius:16px;background:#FBFCFE;border:1px dashed #D8E2F0;padding:18px;overflow:hidden}.bubble{border-radius:18px;background:#F1F5F9;padding:12px 15px;display:inline-block;margin:10px;max-width:65%;font-size:13.5px}.user{text-align:right}.quick-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}.quick{border:1px solid #D8DFEA;border-radius:12px;min-height:40px;display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:750;background:white}.inputbar{min-height:52px;border:1px solid #D8DFEA;border-radius:16px;background:white;display:grid;grid-template-columns:44px 1fr 54px;align-items:center;margin-top:12px}.send{height:40px;width:40px;border-radius:12px;background:var(--blue);color:white!important;display:flex;align-items:center;justify-content:center}.picklist{height:calc(100vh - 176px);min-height:430px;overflow:hidden}.pick{min-height:116px;border:1px solid var(--line);border-radius:16px;padding:13px;background:white;margin-bottom:12px}.footer{text-align:center;color:var(--muted)!important;font-size:11.5px;margin-top:8px}.visit{display:inline-block;margin-top:8px;border:1px solid var(--line);border-radius:10px;padding:7px 10px;font-size:11.5px;background:white}
</style>
""", unsafe_allow_html=True)

left, right = st.columns([0.19, 0.81], gap="small")

with left:
    with st.container(height=720, border=True):
        st.markdown('''
<div class="brand"><div class="pin"></div><div><div class="brand-title">GoAround <span class="green">SG</span></div><div class="subtitle">AI local discovery assistant<br>for useful lobang near you.</div></div></div>
<div class="nav"><div class="active">● GoAround Today</div><div>○ Business Promotion</div><div>○ About Databricks</div></div>
<div class="side-title">My area</div><div class="subtitle">Tell us where you are to get better picks.</div><br>
<div class="field">Auto / Current location</div><div class="field">◎ Detect current location</div><div class="field">Seng Kang, Singapore<br>(1.3871, 103.8915)</div>
<div class="subtitle">Discovery radius: 1.5 km</div><div class="field">────────●────────</div>
<span class="tag">cheap food ×</span><span class="tag">grocery ×</span><span class="tag">event ×</span><span class="tag">deal ×</span>
<div class="field" style="background:#0D6EFD;color:white!important;justify-content:center;font-weight:850;margin-top:12px">💾 Save my area</div>
<div class="subtitle">🛡️ Source-backed. Verify details at source.</div>
''', unsafe_allow_html=True)

with right:
    with st.container(height=720, border=True):
        chat_col, picks_col = st.columns([0.68, 0.32], gap="large")
        with chat_col:
            st.markdown('# Ask GoAround')
            st.caption('Your conversation-style local assistant.')
            st.markdown('<span class="status">☀️ 35.0°C Sunny</span><span class="status">📍 Seng Kang, Singapore</span><span class="status">◎ Within 1.5 km</span>', unsafe_allow_html=True)
            st.markdown('''
<div class="chatbox">
  <div>🤖 <span class="bubble">Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan.</span></div>
  <div class="user"><span class="bubble">Any cheap food spots near me?</span> 👤</div>
  <div>🤖 <span class="bubble">Here are some budget-friendly options near you within 1.5 km.</span></div>
</div>
<div class="quick-grid"><div class="quick">🍴 Eat cheap</div><div class="quick">📅 Weekend events</div><div class="quick">🌧️ Rainy-day ideas</div><div class="quick">🛒 Grocery deals</div></div>
<div class="inputbar"><div style="text-align:center">📎</div><div class="muted">Ask GoAround about this area...</div><div class="send">➤</div></div>
<div class="footer">GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.</div>
''', unsafe_allow_html=True)
        with picks_col:
            st.markdown('## Today’s Picks')
            st.caption('Curated for you based on your area and interests.')
            st.markdown('''
<div class="picklist">
  <div class="pick"><b>🤖 $3.50 Chicken Rice Stall</b><br><span class="muted">Food · Google Maps · 0.4 km</span><br>Popular hawker stall with good reviews.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🎉 Community Flea Market</b><br><span class="muted">Eventbrite · 0.6 km</span><br>Local market with pre-loved deals.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🏷️ NTUC FairPrice Deals</b><br><span class="muted">FairPrice · 0.5 km</span><br>Weekly grocery offers near Sengkang.<br><span class="visit">Visit Website</span></div>
</div>
<div class="footer">More picks⌄</div>
''', unsafe_allow_html=True)
