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
:root{
  color-scheme:light!important;
  --bg:#F4F7FB;
  --text:#172B4D;
  --muted:#667085;
  --line:#E3EAF5;
  --blue:#0D6EFD;
  --green:#10B981;
  --app-h:calc(100dvh - 1.1rem);
  --chat-body-h:clamp(280px, calc(100dvh - 395px), 560px);
  --picks-body-h:clamp(390px, calc(100dvh - 152px), 760px);
}
@supports not (height:100dvh){
  :root{--app-h:calc(100vh - 1.1rem);--chat-body-h:clamp(280px, calc(100vh - 395px), 560px);--picks-body-h:clamp(390px, calc(100vh - 152px), 760px);}
}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="block-container"]{
  background:var(--bg)!important;
  color:var(--text)!important;
  color-scheme:light!important;
  overflow:hidden!important;
}
[data-testid="stHeader"],section[data-testid="stSidebar"]{display:none!important}
.main .block-container{
  max-width:none!important;
  padding:.55rem .75rem .35rem .75rem!important;
  height:100dvh!important;
  overflow:hidden!important;
}
div[data-testid="stHorizontalBlock"]{gap:1rem!important;align-items:stretch!important}
div[data-testid="stVerticalBlock"]{gap:.45rem!important}

/* Important: make accidental/base Streamlit bordered containers invisible.
   Only the three real panels below should look like cards. */
div[data-testid="stVerticalBlockBorderWrapper"]{
  background:transparent!important;
  border-color:transparent!important;
  border-radius:0!important;
  box-shadow:none!important;
  overflow:visible!important;
  height:auto!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sidebar-root),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-card),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.picks-card){
  background:white!important;
  border-color:var(--line)!important;
  border-radius:24px!important;
  box-shadow:0 16px 38px rgba(23,43,77,.08)!important;
  overflow:hidden!important;
  height:var(--app-h)!important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.sidebar-root) > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-card) > div,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.picks-card) > div{
  height:100%!important;
  overflow:hidden!important;
}
.stMarkdown,.stCaption,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important}
.muted,.stCaption,.stCaption *{color:var(--muted)!important}
h1{font-size:clamp(1.65rem,2.2vw,2.05rem)!important;letter-spacing:.01em;margin-bottom:.15rem!important}
h2{font-size:clamp(1.25rem,1.55vw,1.55rem)!important;margin-bottom:.15rem!important}
.brand{display:flex;gap:13px;align-items:center;margin-bottom:clamp(14px,2dvh,20px)}
.pin{width:42px;height:42px;border-radius:50%;background:linear-gradient(145deg,#0D6EFD,#20B2AA);box-shadow:0 10px 22px rgba(13,110,253,.20);flex:0 0 auto}
.brand-title{font-size:21px;font-weight:900;color:#0D2B5C}.green{color:var(--green)!important}
.subtitle{font-size:12.5px;line-height:1.45;color:var(--muted)!important;margin-top:4px}
.nav{border-top:1px solid var(--line);padding-top:14px;margin-top:8px}.nav div{border-radius:13px;padding:10px 12px;font-size:13.5px;font-weight:800;margin-bottom:5px}.active{background:linear-gradient(90deg,#EAF2FF,#F6FAFF);color:#175CD3!important;box-shadow:inset 3px 0 0 #0D6EFD}
.side-title{font-size:20px;font-weight:900;margin:clamp(13px,2dvh,18px) 0 5px 0}
.field{min-height:44px;border:1px solid #D8DFEA;border-radius:13px;background:white;display:flex;align-items:center;padding:0 13px;font-size:12.5px;color:#4B5565!important;margin-bottom:9px;box-shadow:0 2px 8px rgba(23,43,77,.025);box-sizing:border-box}
.location-field{min-height:56px;align-items:flex-start;padding-top:9px;line-height:1.35}
.tag{border-radius:999px;padding:6px 10px;background:#EEF4FF;color:#175CD3!important;font-size:11.5px;font-weight:800;display:inline-block;margin:3px}.tag-wrap{margin:7px 0 12px 0}
.status{display:inline-block;border:1px solid var(--line);border-radius:12px;padding:9px 14px;font-size:12.5px;margin:0 8px 12px 0;background:white;box-shadow:0 2px 8px rgba(23,43,77,.025)}
.chat-card,.picks-card,.sidebar-root{height:100%;box-sizing:border-box;overflow:hidden}
.chatbox{height:var(--chat-body-h);border-radius:18px;background:linear-gradient(180deg,#FFFFFF 0%,#FBFCFE 100%);border:1px dashed #D8E2F0;padding:22px;overflow:hidden;box-sizing:border-box}
.bubble{border-radius:18px;background:#F1F5F9;padding:13px 16px;display:inline-block;margin:12px;max-width:68%;font-size:14px;line-height:1.45;box-shadow:0 2px 8px rgba(23,43,77,.025)}
.user{text-align:right}.quick-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}.quick{border:1px solid #D8DFEA;border-radius:13px;min-height:44px;display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:800;background:white;box-shadow:0 2px 8px rgba(23,43,77,.025)}
.inputbar{min-height:58px;border:1px solid #D8DFEA;border-radius:18px;background:white;display:grid;grid-template-columns:46px 1fr 58px;align-items:center;margin-top:14px;box-shadow:0 6px 18px rgba(23,43,77,.045)}
.send{height:44px;width:44px;border-radius:13px;background:var(--blue);color:white!important;display:flex;align-items:center;justify-content:center;font-weight:900}
.picklist{height:var(--picks-body-h);overflow:hidden}.pick{min-height:clamp(112px,17dvh,135px);border:1px solid var(--line);border-radius:18px;padding:15px;background:white;margin-bottom:13px;box-shadow:0 5px 16px rgba(23,43,77,.045)}.pick b{font-size:15px}
.footer{text-align:center;color:var(--muted)!important;font-size:11.5px;margin-top:9px}.visit{display:inline-block;margin-top:10px;border:1px solid var(--line);border-radius:11px;padding:8px 11px;font-size:11.5px;background:white;color:#0D2B5C!important;font-weight:750}.save{background:linear-gradient(90deg,#0D6EFD,#2563EB)!important;color:white!important;justify-content:center!important;font-weight:900!important;border:0!important;box-shadow:0 8px 18px rgba(13,110,253,.22)!important}.main-shell-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.view-all{font-size:13px;color:#175CD3!important;font-weight:800;margin-top:6px}.sidebar-note{font-size:11.8px;color:var(--muted)!important;margin-top:10px;line-height:1.35}
@media(max-height:760px){:root{--app-h:calc(100dvh - .9rem);--chat-body-h:clamp(260px, calc(100dvh - 405px), 420px);--picks-body-h:clamp(370px, calc(100dvh - 165px), 620px)}.pick{min-height:108px}.inputbar{min-height:52px}.quick{min-height:39px}.brand{margin-bottom:12px}.field{min-height:38px;margin-bottom:7px}.location-field{min-height:48px}.nav div{padding:8px 10px}.tag{padding:5px 8px}.sidebar-note{display:none}}
</style>
""", unsafe_allow_html=True)

left, right = st.columns([0.18, 0.82], gap="small")

with left:
    with st.container(border=True):
        st.markdown('''
<div class="sidebar-root">
<div class="brand"><div class="pin"></div><div><div class="brand-title">GoAround <span class="green">SG</span></div><div class="subtitle">AI local discovery assistant<br>for useful lobang near you.</div></div></div>
<div class="nav"><div class="active">● GoAround Today</div><div>○ Business Promotion</div><div>○ About Databricks</div></div>
<div class="side-title">My area</div><div class="subtitle">Tell us where you are to get better picks.</div><br>
<div class="field">Auto / Current location</div><div class="field">◎ Detect current location</div><div class="field location-field">Seng Kang, Singapore<br>(1.3871, 103.8915)</div>
<div class="subtitle">Discovery radius: 1.5 km</div><div class="field">────────●────────</div>
<div class="tag-wrap"><span class="tag">cheap food ×</span><span class="tag">grocery ×</span><span class="tag">event ×</span><span class="tag">deal ×</span></div>
<div class="field save">💾 Save my area</div>
<div class="sidebar-note">Source-backed. Verify details at source.</div>
</div>
''', unsafe_allow_html=True)

with right:
    chat_col, picks_col = st.columns([0.68, 0.32], gap="large")
    with chat_col:
        with st.container(border=True):
            st.markdown('''
<div class="chat-card">
<h1>Ask GoAround</h1>
<div class="muted">Your conversation-style local assistant.</div>
<div style="margin-top:12px"><span class="status">☀️ 35.0°C Sunny</span><span class="status">📍 Seng Kang, Singapore</span><span class="status">◎ Within 1.5 km</span></div>
<div class="chatbox">
  <div>🤖 <span class="bubble">Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan.</span></div>
  <div class="user"><span class="bubble">Any cheap food spots near me?</span> 👤</div>
  <div>🤖 <span class="bubble">Here are some budget-friendly options near you within 1.5 km.</span></div>
</div>
<div class="quick-grid"><div class="quick">🍴 Eat cheap</div><div class="quick">📅 Weekend events</div><div class="quick">🌧️ Rainy-day ideas</div><div class="quick">🛒 Grocery deals</div></div>
<div class="inputbar"><div style="text-align:center">📎</div><div class="muted">Ask GoAround about this area...</div><div class="send">➤</div></div>
<div class="footer">GoAround SG. Source-backed local discovery only. Verify deals, events and official updates at source before acting.</div>
</div>
''', unsafe_allow_html=True)
    with picks_col:
        with st.container(border=True):
            st.markdown('''
<div class="picks-card">
<div class="main-shell-title"><div><h2>Today’s Picks</h2><div class="muted">Curated for you based on your area and interests.</div></div><div class="view-all">View all</div></div>
<div class="picklist">
  <div class="pick"><b>🤖 $3.50 Chicken Rice Stall</b><br><span class="muted">Food · Google Maps · 0.4 km</span><br>Popular hawker stall with good reviews and long queue.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🎉 Community Flea Market</b><br><span class="muted">Eventbrite · 0.6 km</span><br>Local market with pre-loved deals, snacks and more.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🏷️ NTUC FairPrice Deals</b><br><span class="muted">FairPrice · 0.5 km</span><br>Weekly grocery offers near Sengkang.<br><span class="visit">Visit Website</span></div>
</div>
<div class="footer" style="color:#175CD3!important;font-weight:800">More picks⌄</div>
</div>
''', unsafe_allow_html=True)
