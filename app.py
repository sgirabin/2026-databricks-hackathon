from __future__ import annotations

import math
import os
import re
import urllib.parse
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title='HomeWise SG', page_icon='🏠', layout='wide')

DATASTORE_URL = 'https://data.gov.sg/api/action/datastore_search'
ONEMAP_SEARCH_URL = 'https://www.onemap.gov.sg/api/common/elastic/search'
HDB_RESALE_ID = 'd_8b84c4ee58e3cfc0ece0d773c8ca6abc'
CREDIBLE_DOMAINS = ['channelnewsasia.com','straitstimes.com','businesstimes.com.sg','todayonline.com','mothership.sg','scdf.gov.sg','police.gov.sg','gov.sg','hdb.gov.sg','ura.gov.sg','lta.gov.sg']

SAMPLE_AMENITIES = pd.DataFrame([
    ['hawker_centre','One Punggol Hawker Centre','1 Punggol Drive','828629',1.40850,103.90500],
    ['supermarket','Waterway Point Supermarket','83 Punggol Central','828761',1.40665,103.90220],
    ['community_club','One Punggol Community Club','1 Punggol Drive','828629',1.40850,103.90500],
    ['school','Punggol Green Primary School','98 Punggol Walk','828772',1.40590,103.89980],
    ['preschool','Sample Childcare Centre Punggol','273C Punggol Place','823273',1.40290,103.90260],
    ['hawker_centre','Maxwell Food Centre','1 Kadayanallur Street','069184',1.28030,103.84480],
    ['supermarket','FairPrice Tanjong Pagar','1 Tanjong Pagar Plaza','082001',1.27690,103.84390],
    ['community_club','Tanjong Pagar Community Club','101 Cantonment Road','089774',1.27570,103.84290],
    ['school','Cantonment Primary School','1 Cantonment Close','088256',1.27490,103.83980],
    ['preschool','Sample Childcare Centre Cantonment','1 Cantonment Road','080001',1.27650,103.84080],
], columns=['category','name','address','postal_code','lat','lon'])


def api_headers() -> dict[str, str]:
    headers = {'User-Agent': 'homewise-sg-hackathon/0.1'}
    if os.getenv('DATA_GOV_API_KEY'):
        headers['x-api-key'] = os.getenv('DATA_GOV_API_KEY')
    return headers


@st.cache_data(ttl=86400, show_spinner=False)
def load_hdb_resale(max_records: int = 30000) -> pd.DataFrame:
    rows, offset = [], 0
    while len(rows) < max_records:
        limit = min(5000, max_records - len(rows))
        r = requests.get(DATASTORE_URL, params={'resource_id': HDB_RESALE_ID, 'limit': limit, 'offset': offset}, headers=api_headers(), timeout=45)
        r.raise_for_status()
        result = r.json().get('result', {})
        page = result.get('records', [])
        if not page:
            break
        rows.extend(page)
        offset += len(page)
        if offset >= int(result.get('total', offset)):
            break
    df = pd.DataFrame(rows).drop(columns=['_id'], errors='ignore')
    df.columns = [re.sub(r'[^a-z0-9]+', '_', c.strip().lower()).strip('_') for c in df.columns]
    if 'month' in df.columns:
        df['month'] = pd.to_datetime(df['month'], errors='coerce')
        df['quarter'] = df['month'].dt.to_period('Q').astype(str)
    for c in ['resale_price','floor_area_sqm']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    for c in ['town','flat_type','street_name','block','storey_range']:
        if c in df.columns:
            df[c] = df[c].astype(str).str.upper().str.strip()
    return df


def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={'searchVal': query, 'returnGeom': 'Y', 'getAddrDetails': 'Y', 'pageNum': 1}, timeout=30)
    r.raise_for_status()
    results = r.json().get('results') or []
    if not results:
        raise RuntimeError(f'No OneMap result for {query}')
    best = results[0]
    return {'address': best.get('ADDRESS') or query, 'road_name': best.get('ROAD_NAME') or '', 'postal_code': best.get('POSTAL') or '', 'lat': float(best['LATITUDE']), 'lon': float(best['LONGITUDE'])}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def nearest(df: pd.DataFrame, lat: float, lon: float, radius_m: int) -> pd.DataFrame:
    out = df.copy()
    out['distance_m'] = [haversine_m(lat, lon, r.lat, r.lon) for r in out.itertuples()]
    return out[out.distance_m <= radius_m].sort_values('distance_m').head(10)


def build_trend(df: pd.DataFrame, town: str, flat_type: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    if town != 'Any': out = out[out.town == town]
    if flat_type != 'Any': out = out[out.flat_type == flat_type]
    if out.empty: return out, pd.DataFrame(), {}
    q = out.groupby('quarter', as_index=False).agg(median_price=('resale_price','median'), transactions=('resale_price','size'))
    max_month = out.month.max(); last = out[out.month >= max_month - pd.DateOffset(months=12)]; prev = out[(out.month < max_month - pd.DateOffset(months=12)) & (out.month >= max_month - pd.DateOffset(months=24))]
    last_med = float(last.resale_price.median()) if not last.empty else None; prev_med = float(prev.resale_price.median()) if not prev.empty else None
    yoy = round((last_med-prev_med)/prev_med*100, 1) if last_med and prev_med else None
    latest = q.tail(1).iloc[0].to_dict() if not q.empty else {}
    return out.sort_values('month', ascending=False), q, {'latest_quarter_median': latest.get('median_price'), 'latest_quarter_transactions': int(latest.get('transactions',0)) if latest else 0, 'last_12m_median': last_med, 'yoy_pct': yoy, 'sample_size': len(out)}


def score_home(nearest_by_cat: dict[str, pd.DataFrame], trend: dict[str, Any]) -> dict[str, float]:
    def first(cat): return None if nearest_by_cat.get(cat, pd.DataFrame()).empty else float(nearest_by_cat[cat].iloc[0].distance_m)
    def sdist(d, excellent, good, maxd):
        if d is None: return 40.0
        if d <= excellent: return 100.0
        if d <= good: return 80.0
        if d <= maxd: return max(30.0, 80 - (d-good)/(maxd-good)*50)
        return 10.0
    daily = (sdist(first('hawker_centre'),500,900,2000)+sdist(first('supermarket'),500,900,2000))/2
    edu = (sdist(first('school'),700,1000,2500)+sdist(first('preschool'),500,800,1800))/2
    yoy = trend.get('yoy_pct'); price = 50 if yoy is None else 45 if yoy > 10 else 70 if yoy > 3 else 80 if yoy > -5 else 60
    overall = 0.30*50 + 0.25*daily + 0.20*edu + 0.15*price + 0.10*70
    return {'overall': round(overall,1), 'transport': 50, 'daily_convenience': round(daily,1), 'education': round(edu,1), 'price_trend': price, 'evidence_completeness': 70}


def evidence_links(query: str) -> dict[str, str]:
    q = urllib.parse.quote_plus(query)
    domain_q = ' OR '.join([f'site:{d}' for d in CREDIBLE_DOMAINS])
    return {'Credible web search': 'https://www.google.com/search?q=' + urllib.parse.quote_plus(query + ' ' + domain_q), 'CNA': f'https://www.google.com/search?q={q}+site%3Achannelnewsasia.com', 'Straits Times': f'https://www.google.com/search?q={q}+site%3Astraitstimes.com', 'Official gov search': f'https://www.google.com/search?q={q}+site%3Agov.sg'}


def money(v): return 'n/a' if v is None or pd.isna(v) else f'S${float(v):,.0f}'
def dist(v): return f'{v:,.0f} m' if v < 1000 else f'{v/1000:.1f} km'


st.title('🏠 HomeWise SG')
st.caption('Source-backed Singapore home buyer intelligence using open data + Databricks-ready AI')
with st.sidebar:
    sample = st.selectbox('Try a sample', ['Custom', '308C Punggol Walk', '1 Cantonment Road', '273C Punggol Place'])
    address = st.text_input('Address or postal code', '' if sample == 'Custom' else sample)
    radius = st.slider('Nearby radius', 500, 3000, 1500, 100)
    max_records = st.selectbox('HDB resale rows', [8000, 30000, 100000], index=1)

if not address:
    st.info('Enter an address or postal code to start.')
    st.stop()

try:
    profile = geocode(address)
except Exception as exc:
    st.error(f'Could not geocode with OneMap: {exc}')
    st.stop()

st.success(f"Matched: {profile['address']}")
cols = st.columns(4); cols[0].metric('Postal', profile['postal_code'] or 'n/a'); cols[1].metric('Road', profile['road_name'] or 'n/a'); cols[2].metric('Lat', f"{profile['lat']:.5f}"); cols[3].metric('Lon', f"{profile['lon']:.5f}")

amenities = SAMPLE_AMENITIES
resale = load_hdb_resale(max_records)
nearest_by_cat = {cat: nearest(amenities[amenities.category == cat], profile['lat'], profile['lon'], radius) for cat in amenities.category.unique()}
towns = sorted(resale.town.dropna().unique().tolist()) if not resale.empty else []
flats = sorted(resale.flat_type.dropna().unique().tolist()) if not resale.empty else []

tab1, tab2, tab3, tab4, tab5 = st.tabs(['Overview','Amenities','Price trends','Evidence','Architecture'])
with tab3:
    town = st.selectbox('Town', ['Any'] + towns); flat = st.selectbox('Flat type', ['Any'] + flats)
    filtered, quarterly, trend = build_trend(resale, town, flat)
    a,b,c,d = st.columns(4); a.metric('Latest qtr median', money(trend.get('latest_quarter_median'))); b.metric('Latest qtr txns', trend.get('latest_quarter_transactions',0)); c.metric('Last 12m median', money(trend.get('last_12m_median'))); d.metric('YoY median', 'n/a' if trend.get('yoy_pct') is None else f"{trend['yoy_pct']}%")
    if not quarterly.empty: st.plotly_chart(px.line(quarterly, x='quarter', y='median_price', markers=True), use_container_width=True)
    if not filtered.empty: st.dataframe(filtered[[c for c in ['month','town','flat_type','block','street_name','storey_range','floor_area_sqm','remaining_lease','resale_price'] if c in filtered.columns]].head(30), use_container_width=True, hide_index=True)

score = score_home(nearest_by_cat, trend if 'trend' in locals() else {})
with tab1:
    left, right = st.columns([1,2])
    with left:
        st.subheader('Buyer scorecard'); st.metric('Overall', f"{score['overall']}/100"); st.progress(score['overall']/100)
        for k,v in score.items():
            if k != 'overall': st.write(f"**{k.replace('_',' ').title()}**: {v}/100")
    with right:
        st.subheader('Buyer briefing')
        st.write(f"For {profile['address']}, HomeWise gives a directional score of {score['overall']}/100. Price YoY is {'n/a' if trend.get('yoy_pct') is None else str(trend.get('yoy_pct')) + '%'}. Verify walking route, school rules, noise, same-block transactions, and official future plans before making an offer.")
        st.warning('Prototype only. Not financial, legal, valuation, or property advice.')

with tab2:
    for cat, df in nearest_by_cat.items():
        st.subheader(cat.replace('_',' ').title())
        if df.empty: st.info('No sample result within selected radius.')
        else:
            out = df.copy(); out['distance'] = out.distance_m.apply(dist)
            st.dataframe(out[['name','distance','address','postal_code']], use_container_width=True, hide_index=True)
    map_df = pd.concat([df.head(5) for df in nearest_by_cat.values() if not df.empty], ignore_index=True)
    if not map_df.empty: st.map(map_df.rename(columns={'lat':'latitude','lon':'longitude'})[['latitude','longitude']])

with tab4:
    st.subheader('Sensitive history — credible source only')
    st.caption('No source URL = no claim. This avoids unsupported fire/suicide/crime/death/stigma statements.')
    q = f'"{profile["address"]}" (fire OR suicide OR death OR crime OR police OR SCDF) Singapore'
    for label, link in evidence_links(q).items(): st.markdown(f'- [{label}]({link})')
    st.subheader('Future development checks')
    st.markdown('- [URA Draft Master Plan](https://www.uradraftmasterplan.gov.sg/)\n- [LTA Upcoming Projects](https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html)\n- [OneMap](https://www.onemap.gov.sg/)')

with tab5:
    st.subheader('Databricks architecture')
    st.code('Open data APIs -> Databricks notebooks -> Bronze Delta -> Silver cleaned tables -> Gold buyer features/views -> Databricks App + Genie + Model Serving + optional Lakebase')
    st.dataframe(pd.DataFrame([{'source': 'HDB resale transactions', 'dataset_id': HDB_RESALE_ID, 'agency': 'HDB'}, {'source': 'OneMap geocoding', 'dataset_id': 'OneMap API', 'agency': 'SLA'}]), use_container_width=True, hide_index=True)
