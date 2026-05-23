from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="LAYOUT TARGET - GoAround SG",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FOOTER = "GoAround SG. Source-backed local discovery. Verify details at source. Team R4131N."

st.markdown(
    """
<style>
:root {
  color-scheme: light !important;
  --bg: #F7FAFC;
  --panel: #FFFFFF;
  --text: #172B4D;
  --muted: #667085;
  --line: #E6EAF2;
  --blue: #0D6EFD;
  --green: #10B981;
  --soft: #F3F7FC;
}

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="block-container"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  color-scheme: light !important;
}

[data-testid="stHeader"], section[data-testid="stSidebar"] {
  display: none !important;
}

.main .block-container {
  max-width: none !important;
  padding: 0 !important;
}

.app-shell {
  width: 100vw;
  height: 100vh;
  display: grid;
  grid-template-columns: 290px minmax(0, 1fr);
  gap: 0;
  overflow: hidden;
  background: var(--bg);
}

.left-panel {
  height: 100vh;
  padding: 18px 18px 16px 18px;
  box-sizing: border-box;
  background: #F4F7FB;
  border-right: 1px solid #E5EAF3;
  overflow: hidden;
}

.sidebar-card {
  height: calc(100vh - 34px);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: 0 12px 30px rgba(23,43,77,.06);
  padding: 20px 18px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: hidden;
}

.right-panel {
  height: 100vh;
  padding: 18px 24px 16px 24px;
  box-sizing: border-box;
  overflow: hidden;
}

.main-card {
  height: calc(100vh - 34px);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: 0 12px 30px rgba(23,43,77,.06);
  padding: 20px 22px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 330px;
  gap: 22px;
  overflow: hidden;
}

.chat-panel, .picks-panel {
  height: 100%;
  min-height: 0;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 8px 22px rgba(23,43,77,.04);
  padding: 22px;
  box-sizing: border-box;
  overflow: hidden;
}

.chat-panel {
  display: grid;
  grid-template-rows: auto auto 1fr auto auto;
  gap: 14px;
}

.picks-panel {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 14px;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
}

.pin {
  width: 40px;
  height: 40px;
  border-radius: 50% 50% 50% 9px;
  background: linear-gradient(145deg,#0D6EFD,#20B2AA);
  transform: rotate(-45deg);
  position: relative;
  box-shadow: 0 8px 18px rgba(13,110,253,.18);
  flex: 0 0 auto;
}
.pin:after {
  content: "";
  width: 16px;
  height: 16px;
  background: #fff;
  border-radius: 50%;
  position: absolute;
  left: 12px;
  top: 12px;
}

h1, h2, h3, p { margin: 0; }
.brand h1 { font-size: 21px; color: #0D2B5C; font-weight: 850; }
.brand h1 b { color: var(--green); }
.brand p, .muted { color: var(--muted); font-size: 13px; line-height: 1.4; }

.nav-list {
  display: grid;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.nav-item {
  border-radius: 12px;
  padding: 10px 12px;
  background: transparent;
  color: var(--text);
  font-weight: 650;
  font-size: 14px;
}
.nav-item.active { background: #EEF4FF; color: #175CD3; }

.area-block {
  border-top: 1px solid var(--line);
  padding-top: 16px;
  display: grid;
  gap: 12px;
}
.field {
  min-height: 42px;
  border: 1px solid #D8DFEA;
  border-radius: 12px;
  background: #FFFFFF;
  display: flex;
  align-items: center;
  padding: 0 12px;
  color: var(--muted);
  font-size: 13px;
}
.tag-row { display: flex; gap: 7px; flex-wrap: wrap; }
.tag {
  border-radius: 999px;
  padding: 6px 10px;
  background: #EEF4FF;
  color: #175CD3;
  font-size: 12px;
  font-weight: 700;
}
.primary-btn {
  min-height: 42px;
  border-radius: 12px;
  background: var(--blue);
  color: #fff;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: auto;
}

.status-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.status-pill {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 9px 14px;
  font-size: 13px;
  color: var(--text);
  background: #FFFFFF;
}
.chat-body {
  min-height: 0;
  border-radius: 16px;
  background: linear-gradient(180deg,#FFFFFF 0%,#FBFCFE 100%);
  border: 1px dashed #D8E2F0;
  padding: 18px;
  display: grid;
  align-content: start;
  gap: 16px;
  overflow: hidden;
}
.message-row { display: flex; gap: 12px; align-items: flex-start; }
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #EEF4FF;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}
.bubble {
  max-width: 68%;
  border-radius: 18px;
  background: #F1F5F9;
  padding: 13px 16px;
  color: var(--text);
  line-height: 1.45;
  font-size: 14px;
}
.message-row.user { justify-content: flex-end; }
.message-row.user .bubble { background: #EEF4FF; }
.quick-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 10px;
}
.quick {
  border: 1px solid #D8DFEA;
  border-radius: 12px;
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  background: #FFFFFF;
}
.input-row {
  min-height: 58px;
  border: 1px solid #D8DFEA;
  border-radius: 16px;
  background: #FFFFFF;
  display: grid;
  grid-template-columns: 44px 1fr 54px;
  align-items: center;
  overflow: hidden;
}
.input-icon, .send-icon { text-align: center; color: var(--muted); }
.send-icon {
  height: 44px;
  width: 44px;
  border-radius: 12px;
  background: var(--blue);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  justify-self: center;
  font-weight: 900;
}
.footer-note { text-align: center; color: var(--muted); font-size: 12px; }

.picks-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.picks-list {
  min-height: 0;
  overflow: hidden;
  display: grid;
  gap: 12px;
}
.pick-card {
  min-height: 118px;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 14px;
  display: grid;
  grid-template-columns: 42px 1fr;
  gap: 12px;
  background: #FFFFFF;
}
.pick-icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #F1F5F9;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pick-title { font-weight: 850; font-size: 15px; margin-bottom: 5px; }
.pick-meta { color: var(--muted); font-size: 12px; margin-top: 8px; }
.pick-actions { display: flex; gap: 8px; margin-top: 10px; }
.small-btn {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 7px 10px;
  font-size: 12px;
  background: #FFFFFF;
}
.more-btn {
  border-top: 1px solid var(--line);
  text-align: center;
  padding-top: 12px;
  color: #175CD3;
  font-weight: 800;
}

@media (max-width: 1100px) {
  .app-shell { grid-template-columns: 250px minmax(0, 1fr); }
  .main-card { grid-template-columns: minmax(0, 1fr) 300px; gap: 16px; padding: 16px; }
  .chat-panel, .picks-panel { padding: 16px; }
  .quick-row { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="app-shell">
  <aside class="left-panel">
    <div class="sidebar-card">
      <div class="brand">
        <div class="pin"></div>
        <div>
          <h1>GoAround <b>SG</b></h1>
          <p>AI local discovery assistant<br/>for useful lobang near you.</p>
        </div>
      </div>

      <div class="nav-list">
        <div class="nav-item active">● GoAround Today</div>
        <div class="nav-item">○ Business Promotion</div>
        <div class="nav-item">○ About Databricks</div>
      </div>

      <div class="area-block">
        <h3>My area</h3>
        <p class="muted">Tell us where you are to get better picks.</p>
        <div class="field">Auto / Current location</div>
        <div class="field">◎ Detect current location</div>
        <div class="field">Seng Kang, Singapore<br/>(1.3871, 103.8915)</div>
        <p class="muted">Discovery radius: 1.5 km</p>
        <div class="field">────────●────────</div>
        <div class="tag-row">
          <span class="tag">cheap food ×</span>
          <span class="tag">grocery ×</span>
          <span class="tag">event ×</span>
          <span class="tag">deal ×</span>
        </div>
      </div>

      <div class="primary-btn">💾 Save my area</div>
      <p class="muted">🛡️ Source-backed. Verify details at source.</p>
    </div>
  </aside>

  <main class="right-panel">
    <div class="main-card">
      <section class="chat-panel">
        <div>
          <h2>Ask GoAround</h2>
          <p class="muted">Your conversation-style local assistant.</p>
        </div>
        <div class="status-row">
          <div class="status-pill">☀️ 35.0°C Sunny</div>
          <div class="status-pill">📍 Seng Kang, Singapore</div>
          <div class="status-pill">◎ Within 1.5 km</div>
        </div>
        <div class="chat-body">
          <div class="message-row">
            <div class="avatar">🤖</div>
            <div class="bubble">Hi, I’m Ask GoAround. Ask me what to eat, what to do with kids, rainy-day options, nearby deals, or a short visitor plan.</div>
          </div>
          <div class="message-row user">
            <div class="bubble">Any cheap food spots near me?</div>
            <div class="avatar">👤</div>
          </div>
          <div class="message-row">
            <div class="avatar">🤖</div>
            <div class="bubble">Here are some budget-friendly options near you within 1.5 km.</div>
          </div>
        </div>
        <div class="quick-row">
          <div class="quick">🍴 Eat cheap</div>
          <div class="quick">📅 Weekend events</div>
          <div class="quick">🌧️ Rainy-day ideas</div>
          <div class="quick">🛒 Grocery deals</div>
        </div>
        <div>
          <div class="input-row">
            <div class="input-icon">📎</div>
            <div class="muted">Ask GoAround about this area...</div>
            <div class="send-icon">➤</div>
          </div>
          <div class="footer-note">{FOOTER}</div>
        </div>
      </section>

      <aside class="picks-panel">
        <div class="picks-header">
          <div>
            <h2>Today’s Picks</h2>
            <p class="muted">Curated for you based on your area and interests.</p>
          </div>
          <div class="muted">View all</div>
        </div>
        <div class="picks-list">
          <div class="pick-card">
            <div class="pick-icon">🤖</div>
            <div>
              <p class="muted">FOOD</p>
              <div class="pick-title">$3.50 Chicken Rice Stall</div>
              <p class="muted">Popular hawker stall with good reviews and queue.</p>
              <div class="pick-meta">Google Maps · 0.4 km</div>
              <div class="pick-actions"><span class="small-btn">🔖</span><span class="small-btn">↗</span><span class="small-btn">Visit Website</span></div>
            </div>
          </div>
          <div class="pick-card">
            <div class="pick-icon">🎉</div>
            <div>
              <p class="muted">EVENT</p>
              <div class="pick-title">Community Flea Market</div>
              <p class="muted">Local market with pre-loved deals, snacks and more.</p>
              <div class="pick-meta">Eventbrite · 0.6 km</div>
              <div class="pick-actions"><span class="small-btn">🔖</span><span class="small-btn">↗</span><span class="small-btn">Visit Website</span></div>
            </div>
          </div>
          <div class="pick-card">
            <div class="pick-icon">🏷️</div>
            <div>
              <p class="muted">DEAL</p>
              <div class="pick-title">NTUC FairPrice Deals</div>
              <p class="muted">Weekly offers on groceries near Sengkang.</p>
              <div class="pick-meta">NTUC FairPrice · 0.5 km</div>
              <div class="pick-actions"><span class="small-btn">🔖</span><span class="small-btn">↗</span><span class="small-btn">Visit Website</span></div>
            </div>
          </div>
        </div>
        <div class="more-btn">More picks⌄</div>
      </aside>
    </div>
  </main>
</div>
""",
    unsafe_allow_html=True,
)
