from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="LAYOUT TARGET - GoAround SG",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

page = st.query_params.get("page", "today")
if page not in {"today", "business", "about"}:
    page = "today"

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
  --app-h:calc(100dvh - 1.05rem);
  --chat-body-h:clamp(280px, calc(100dvh - 395px), 560px);
  --picks-body-h:clamp(390px, calc(100dvh - 152px), 760px);
}
@supports not (height:100dvh){
  :root{--app-h:calc(100vh - 1.05rem);--chat-body-h:clamp(280px, calc(100vh - 395px), 560px);--picks-body-h:clamp(390px, calc(100vh - 152px), 760px);}
}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="block-container"]{background:var(--bg)!important;color:var(--text)!important;color-scheme:light!important;overflow:hidden!important}
[data-testid="stHeader"],section[data-testid="stSidebar"]{display:none!important}
.main .block-container{max-width:none!important;padding:.55rem .75rem .35rem .75rem!important;height:100dvh!important;overflow:hidden!important}
div[data-testid="stHorizontalBlock"]{gap:1rem!important;align-items:stretch!important}
div[data-testid="stVerticalBlock"]{gap:0!important}
.app-card{height:var(--app-h);background:white;border:1px solid var(--line);border-radius:24px;box-shadow:0 16px 38px rgba(23,43,77,.08);overflow:hidden;box-sizing:border-box}
.sidebar-card{padding:26px 24px 18px 24px}.chat-card{padding:28px 28px 18px 28px}.picks-card{padding:28px 24px 18px 24px}.full-card{padding:30px 32px 20px 32px}
.stMarkdown,.stCaption,label,p,span,div,h1,h2,h3,h4,h5,h6,li{color:var(--text)!important}.muted,.stCaption,.stCaption *{color:var(--muted)!important}
h1{font-size:clamp(1.65rem,2.2vw,2.05rem)!important;letter-spacing:.01em;margin:0 0 .15rem 0!important}h2{font-size:clamp(1.25rem,1.55vw,1.55rem)!important;margin:0 0 .15rem 0!important}
.brand{display:flex;gap:13px;align-items:center;margin-bottom:clamp(14px,2dvh,20px)}.pin{width:42px;height:42px;border-radius:50%;background:linear-gradient(145deg,#0D6EFD,#20B2AA);box-shadow:0 10px 22px rgba(13,110,253,.20);flex:0 0 auto}.brand-title{font-size:21px;font-weight:900;color:#0D2B5C}.green{color:var(--green)!important}.subtitle{font-size:12.5px;line-height:1.45;color:var(--muted)!important;margin-top:4px}
.nav{border-top:1px solid var(--line);padding-top:14px;margin-top:8px}.nav a{display:block;text-decoration:none!important;border-radius:13px;padding:10px 12px;font-size:13.5px;font-weight:800;margin-bottom:5px;color:var(--text)!important}.nav a.active{background:linear-gradient(90deg,#EAF2FF,#F6FAFF);color:#175CD3!important;box-shadow:inset 3px 0 0 #0D6EFD}
.side-title{font-size:20px;font-weight:900;margin:clamp(13px,2dvh,18px) 0 5px 0}.field{min-height:44px;border:1px solid #D8DFEA;border-radius:13px;background:white;display:flex;align-items:center;padding:0 13px;font-size:12.5px;color:#4B5565!important;margin-bottom:9px;box-shadow:0 2px 8px rgba(23,43,77,.025);box-sizing:border-box}.location-field{min-height:56px;align-items:flex-start;padding-top:9px;line-height:1.35}.tag{border-radius:999px;padding:6px 10px;background:#EEF4FF;color:#175CD3!important;font-size:11.5px;font-weight:800;display:inline-block;margin:3px}.tag-wrap{margin:7px 0 12px 0}
.status{display:inline-block;border:1px solid var(--line);border-radius:12px;padding:9px 14px;font-size:12.5px;margin:0 8px 12px 0;background:white;box-shadow:0 2px 8px rgba(23,43,77,.025)}.chatbox{height:var(--chat-body-h);border-radius:18px;background:linear-gradient(180deg,#FFFFFF 0%,#FBFCFE 100%);border:1px dashed #D8E2F0;padding:22px;overflow:hidden;box-sizing:border-box}.bubble{border-radius:18px;background:#F1F5F9;padding:13px 16px;display:inline-block;margin:12px;max-width:68%;font-size:14px;line-height:1.45;box-shadow:0 2px 8px rgba(23,43,77,.025)}.user{text-align:right}.quick-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}.quick{border:1px solid #D8DFEA;border-radius:13px;min-height:44px;display:flex;align-items:center;justify-content:center;font-size:12.5px;font-weight:800;background:white;box-shadow:0 2px 8px rgba(23,43,77,.025)}.inputbar{min-height:58px;border:1px solid #D8DFEA;border-radius:18px;background:white;display:grid;grid-template-columns:46px 1fr 58px;align-items:center;margin-top:14px;box-shadow:0 6px 18px rgba(23,43,77,.045)}.send{height:44px;width:44px;border-radius:13px;background:var(--blue);color:white!important;display:flex;align-items:center;justify-content:center;font-weight:900}
.picklist{height:var(--picks-body-h);overflow:hidden}.pick{min-height:clamp(112px,17dvh,135px);border:1px solid var(--line);border-radius:18px;padding:15px;background:white;margin-bottom:13px;box-shadow:0 5px 16px rgba(23,43,77,.045)}.pick b{font-size:15px}.footer{text-align:center;color:var(--muted)!important;font-size:11.5px;margin-top:9px}.visit{display:inline-block;margin-top:10px;border:1px solid var(--line);border-radius:11px;padding:8px 11px;font-size:11.5px;background:white;color:#0D2B5C!important;font-weight:750}.save{background:linear-gradient(90deg,#0D6EFD,#2563EB)!important;color:white!important;justify-content:center!important;font-weight:900!important;border:0!important;box-shadow:0 8px 18px rgba(13,110,253,.22)!important}.main-shell-title{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.view-all{font-size:13px;color:#175CD3!important;font-weight:800;margin-top:6px}.sidebar-note{font-size:11.8px;color:var(--muted)!important;margin-top:10px;line-height:1.35}
.kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.kpi{border:1px solid var(--line);border-radius:16px;padding:14px;background:#fff;box-shadow:0 5px 16px rgba(23,43,77,.045)}.kpi b{display:block;font-size:1.35rem;margin-top:4px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.form-field{border:1px solid #D8DFEA;border-radius:13px;padding:12px;background:#fff;color:#4B5565!important;font-size:13px}.wide{grid-column:1/-1}.preview-card{border:1px solid var(--line);border-radius:22px;padding:18px;background:#fff;box-shadow:0 8px 22px rgba(23,43,77,.055);margin-top:14px}.about-section{margin-top:22px}.about-section h2{margin-bottom:8px!important}.about-section ul{margin-top:8px;line-height:1.8}
@media(max-height:760px){:root{--app-h:calc(100dvh - .9rem);--chat-body-h:clamp(260px, calc(100dvh - 405px), 420px);--picks-body-h:clamp(370px, calc(100dvh - 165px), 620px)}.pick{min-height:108px}.inputbar{min-height:52px}.quick{min-height:39px}.brand{margin-bottom:12px}.field{min-height:38px;margin-bottom:7px}.location-field{min-height:48px}.nav a{padding:8px 10px}.tag{padding:5px 8px}.sidebar-note{display:none}.sidebar-card,.chat-card,.picks-card,.full-card{padding-top:22px}}
</style>
""", unsafe_allow_html=True)

def active(name: str) -> str:
    return "active" if page == name else ""

left, right = st.columns([0.18, 0.82], gap="small")

with left:
    st.markdown(f'''
<div class="app-card sidebar-card">
<div class="brand"><div class="pin"></div><div><div class="brand-title">GoAround <span class="green">SG</span></div><div class="subtitle">AI local discovery assistant<br>for useful lobang near you.</div></div></div>
<div class="nav"><a class="{active('today')}" href="?page=today">● GoAround Today</a><a class="{active('business')}" href="?page=business">○ Business Promotion</a><a class="{active('about')}" href="?page=about">○ What is GoAround?</a></div>
<div class="side-title">My area</div><div class="subtitle">Tell us where you are to get better picks.</div><br>
<div class="field">Auto / Current location</div><div class="field">◎ Detect current location</div><div class="field location-field">Seng Kang, Singapore<br>(1.3871, 103.8915)</div>
<div class="subtitle">Discovery radius: 1.5 km</div><div class="field">────────●────────</div>
<div class="tag-wrap"><span class="tag">cheap food ×</span><span class="tag">grocery ×</span><span class="tag">event ×</span><span class="tag">deal ×</span></div>
<div class="field save">💾 Save my area</div>
<div class="sidebar-note">Source-backed. Verify details at source.</div>
</div>
''', unsafe_allow_html=True)

with right:
    if page == "today":
        chat_col, picks_col = st.columns([0.68, 0.32], gap="large")
        with chat_col:
            st.markdown('''
<div class="app-card chat-card">
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
            st.markdown('''
<div class="app-card picks-card">
<div class="main-shell-title"><div><h2>Today’s Picks</h2><div class="muted">Curated for you based on your area and interests.</div></div><div class="view-all">View all</div></div>
<div class="picklist">
  <div class="pick"><b>🤖 $3.50 Chicken Rice Stall</b><br><span class="muted">Food · Google Maps · 0.4 km</span><br>Popular hawker stall with good reviews and long queue.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🎉 Community Flea Market</b><br><span class="muted">Eventbrite · 0.6 km</span><br>Local market with pre-loved deals, snacks and more.<br><span class="visit">Visit Website</span></div>
  <div class="pick"><b>🏷️ NTUC FairPrice Deals</b><br><span class="muted">FairPrice · 0.5 km</span><br>Weekly grocery offers near Sengkang.<br><span class="visit">Visit Website</span></div>
</div>
<div class="footer" style="color:#175CD3!important;font-weight:800">More picks⌄</div>
</div>
''', unsafe_allow_html=True)
    elif page == "business":
        form_col, preview_col = st.columns([0.68, 0.32], gap="large")
        with form_col:
            st.markdown('''
<div class="app-card chat-card">
<h1>Business Promotion</h1>
<div class="muted">Create a local promotion that can appear in Today’s Picks.</div>
<div class="kpi-grid"><div class="kpi"><span class="muted">Active</span><b>3</b></div><div class="kpi"><span class="muted">Clicks</span><b>128</b></div><div class="kpi"><span class="muted">Saves</span><b>47</b></div><div class="kpi"><span class="muted">Views</span><b>612</b></div></div>
<h2>Create Promotion</h2>
<div class="form-grid"><div class="form-field">Business name</div><div class="form-field">Promotion title</div><div class="form-field">Category</div><div class="form-field">Location / Area</div><div class="form-field">Valid from</div><div class="form-field">Valid to</div><div class="form-field wide">Audience / Interests</div><div class="form-field wide" style="min-height:90px;align-items:flex-start">Short description</div><div class="form-field wide">CTA link</div></div>
<div class="field save" style="max-width:220px;margin-top:16px">Publish Promotion</div>
<div class="footer">Business layout placeholder only. Save logic comes later.</div>
</div>
''', unsafe_allow_html=True)
        with preview_col:
            st.markdown('''
<div class="app-card picks-card">
<h2>Preview</h2><div class="muted">How your promotion appears to nearby users.</div>
<div class="preview-card"><div class="tag">FOOD & DINING</div><h2 style="margin-top:16px!important">50% Off Chicken Rice</h2><div class="muted">Fresh chicken, fragrant rice and homemade chilli.</div><br><span class="status">📍 Sengkang</span><br><span class="visit">View details ↗</span></div>
</div>
''', unsafe_allow_html=True)
    else:
        st.markdown('''
<div class="app-card full-card">
<h1>What is GoAround SG?</h1>
<div class="muted">A source-backed local discovery assistant for Singapore.</div>
<div class="about-section"><h2>For residents and visitors</h2><p>Ask what to eat, what to do with kids, rainy-day options, nearby deals, or useful updates around your selected area.</p></div>
<div class="about-section"><h2>For businesses</h2><p>Businesses can create local promotion cards that are shown to nearby users based on location, category, interests, and timing.</p></div>
<div class="about-section"><h2>Why it is different</h2><p>GoAround SG combines open data, source registries, location, weather, ranking, and AI conversation into one daily local assistant.</p></div>
<div class="about-section"><h2>Databricks usage in this prototype</h2><ul><li>Databricks Apps hosts the application.</li><li>Lakehouse / Delta can store Bronze, Silver, and Gold local discovery data.</li><li>Databricks SQL warehouse can serve candidate cards when configured.</li><li>Model Serving / GenAI can power Ask GoAround when a serving endpoint is configured.</li></ul></div>
<div class="footer">GoAround SG — Team R4131N. Source-backed local discovery. Verify final details at source.</div>
</div>
''', unsafe_allow_html=True)
