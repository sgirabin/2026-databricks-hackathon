from __future__ import annotations

import math
import os
import re
import time
import urllib.parse
from typing import Any

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="HomeWise SG", page_icon="🏠", layout="wide")

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
ONEMAP_SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"

DATASETS = {
    "hdb_resale": "d_8b84c4ee58e3cfc0ece0d773c8ca6abc",
    "hawker_centres": "d_4a086da0a5553be1d89383cd90d07ecd",
    "schools": "d_688b934f82c1059ed0a6993d2a829089",
    "preschools": "d_696c994c50745b079b3684f0e90ffc53",
    "community_clubs": "d_f706de1427279e61fe41e89e24d440fa",
    "supermarkets": "d_cac2c32f01960a3ad7202a99c27268a0",
}

CREDIBLE_DOMAINS = [
    "channelnewsasia.com", "straitstimes.com", "businesstimes.com.sg", "todayonline.com",
    "mothership.sg", "scdf.gov.sg", "police.gov.sg", "gov.sg", "hdb.gov.sg", "ura.gov.sg", "lta.gov.sg",
]

PERSONA_WEIGHTS = {
    "Balanced buyer": {"transport": 0.25, "daily": 0.25, "education": 0.15, "price": 0.25, "evidence": 0.10},
    "Family with young child": {"transport": 0.20, "daily": 0.20, "education": 0.30, "price": 0.20, "evidence": 0.10},
    "Car-free commuter": {"transport": 0.40, "daily": 0.20, "education": 0.05, "price": 0.25, "evidence": 0.10},
    "Investor / liquidity focused": {"transport": 0.20, "daily": 0.15, "education": 0.05, "price": 0.50, "evidence": 0.10},
    "Elderly parents nearby": {"transport": 0.20, "daily": 0.35, "education": 0.05, "price": 0.20, "evidence": 0.20},
}


def api_headers() -> dict[str, str]:
    headers = {"User-Agent": "homewise-sg-hackathon/0.2"}
    if os.getenv("DATA_GOV_API_KEY"):
        headers["x-api-key"] = os.getenv("DATA_GOV_API_KEY", "")
    return headers


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in out.columns]
    return out.drop(columns=["_id"], errors="ignore")


@st.cache_data(ttl=86400, show_spinner=False)
def datastore_search(dataset_id: str, limit: int = 5000, max_records: int | None = None) -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        page_limit = limit if max_records is None else min(limit, max_records - len(rows))
        if page_limit <= 0:
            break
        r = requests.get(
            DATASTORE_URL,
            params={"resource_id": dataset_id, "limit": page_limit, "offset": offset},
            headers=api_headers(),
            timeout=45,
        )
        r.raise_for_status()
        result = r.json().get("result", {})
        page = result.get("records", [])
        rows.extend(page)
        offset += len(page)
        if not page or offset >= int(result.get("total", offset)):
            break
    return clean_columns(pd.DataFrame(rows))


@st.cache_data(ttl=86400, show_spinner=False)
def poll_download(dataset_id: str) -> str:
    r = requests.get(POLL_DOWNLOAD_URL.format(dataset_id=dataset_id), headers=api_headers(), timeout=45)
    r.raise_for_status()
    return r.json()["data"]["url"]


def first_value(props: dict[str, Any], candidates: list[str], default: str = "") -> str:
    lower = {str(k).lower(): v for k, v in props.items()}
    for c in candidates:
        if c.lower() in lower and pd.notna(lower[c.lower()]) and str(lower[c.lower()]).strip():
            return str(lower[c.lower()]).strip()
    return default


@st.cache_data(ttl=86400, show_spinner=False)
def load_geojson_points(dataset_id: str, category: str) -> pd.DataFrame:
    try:
        url = poll_download(dataset_id)
        gj = requests.get(url, headers=api_headers(), timeout=90).json()
        rows = []
        for feature in gj.get("features", []):
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates") or []
            if geom.get("type") == "Point" and len(coords) >= 2:
                props = feature.get("properties") or {}
                name = first_value(props, ["name", "NAME", "ADDRESSBUILDINGNAME", "DESCRIPTION"], category)
                block = first_value(props, ["ADDRESSBLOCKHOUSENUMBER", "block"], "")
                street = first_value(props, ["ADDRESSSTREETNAME", "street", "address"], "")
                postal = first_value(props, ["ADDRESSPOSTALCODE", "postal_code", "postal"], "")
                address = " ".join([block, street]).strip() or first_value(props, ["ADDRESS", "description"], "")
                rows.append({
                    "category": category, "name": name, "address": address, "postal_code": postal,
                    "lat": float(coords[1]), "lon": float(coords[0]), "source": "data.gov.sg",
                })
        return pd.DataFrame(rows)
    except Exception as exc:
        st.toast(f"Could not load {category} GeoJSON live data: {exc}", icon="⚠️")
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(query: str) -> dict[str, Any]:
    r = requests.get(ONEMAP_SEARCH_URL, params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=30)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise RuntimeError(f"No OneMap result for {query}")
    best = results[0]
    return {
        "address": best.get("ADDRESS") or query,
        "building": best.get("BUILDING") or "",
        "road_name": best.get("ROAD_NAME") or "",
        "postal_code": best.get("POSTAL") or "",
        "lat": float(best["LATITUDE"]),
        "lon": float(best["LONGITUDE"]),
    }


@st.cache_data(ttl=86400, show_spinner=False)
def geocode_many(rows: list[dict[str, str]], category: str, max_rows: int) -> pd.DataFrame:
    out = []
    for i, item in enumerate(rows[:max_rows]):
        query = item.get("query") or item.get("address") or item.get("name", "")
        if not query:
            continue
        try:
            g = geocode(query)
            out.append({
                "category": category,
                "name": item.get("name") or g.get("building") or query,
                "address": item.get("address") or g["address"],
                "postal_code": item.get("postal_code") or g.get("postal_code", ""),
                "lat": g["lat"],
                "lon": g["lon"],
                "source": item.get("source", "data.gov.sg + OneMap geocode"),
            })
        except Exception:
            pass
        if i % 20 == 19:
            time.sleep(0.2)
    return pd.DataFrame(out)


@st.cache_data(ttl=86400, show_spinner=False)
def load_schools(max_geocode_rows: int = 400) -> pd.DataFrame:
    df = datastore_search(DATASETS["schools"], max_records=800)
    if df.empty:
        return pd.DataFrame()
    name_col = next((c for c in ["school_name", "name"] if c in df.columns), None)
    address_col = next((c for c in ["address", "school_address"] if c in df.columns), None)
    postal_col = next((c for c in ["postal_code", "postal"] if c in df.columns), None)
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "lng"] if c in df.columns), None)
    if lat_col and lon_col and name_col:
        return pd.DataFrame({
            "category": "school", "name": df[name_col],
            "address": df[address_col] if address_col else "", "postal_code": df[postal_col] if postal_col else "",
            "lat": pd.to_numeric(df[lat_col], errors="coerce"), "lon": pd.to_numeric(df[lon_col], errors="coerce"),
            "source": "data.gov.sg",
        }).dropna(subset=["lat", "lon"])
    items = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        address = str(row.get(address_col, "")).strip() if address_col else ""
        postal = str(row.get(postal_col, "")).strip() if postal_col else ""
        query = postal or address or name
        if name and query:
            items.append({"name": name, "address": address, "postal_code": postal, "query": query})
    return geocode_many(items, "school", max_geocode_rows)


@st.cache_data(ttl=86400, show_spinner=False)
def load_preschools(max_geocode_rows: int = 700) -> pd.DataFrame:
    df = datastore_search(DATASETS["preschools"], max_records=2000)
    if df.empty:
        return pd.DataFrame()
    name_col = next((c for c in ["centre_name", "center_name", "name"] if c in df.columns), None)
    address_col = next((c for c in ["centre_address", "address"] if c in df.columns), None)
    postal_col = next((c for c in ["postal_code", "postal"] if c in df.columns), None)
    lat_col = next((c for c in ["latitude", "lat"] if c in df.columns), None)
    lon_col = next((c for c in ["longitude", "lon", "lng"] if c in df.columns), None)
    if lat_col and lon_col and name_col:
        return pd.DataFrame({
            "category": "preschool", "name": df[name_col],
            "address": df[address_col] if address_col else "", "postal_code": df[postal_col] if postal_col else "",
            "lat": pd.to_numeric(df[lat_col], errors="coerce"), "lon": pd.to_numeric(df[lon_col], errors="coerce"),
            "source": "data.gov.sg",
        }).dropna(subset=["lat", "lon"])
    items = []
    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).strip() if name_col else ""
        address = str(row.get(address_col, "")).strip() if address_col else ""
        postal = str(row.get(postal_col, "")).strip() if postal_col else ""
        query = postal or address or name
        if name and query:
            items.append({"name": name, "address": address, "postal_code": postal, "query": query})
    return geocode_many(items, "preschool", max_geocode_rows)


@st.cache_data(ttl=86400, show_spinner=True)
def load_live_amenities(max_school_geocode: int, max_preschool_geocode: int) -> pd.DataFrame:
    frames = [
        load_geojson_points(DATASETS["hawker_centres"], "hawker_centre"),
        load_geojson_points(DATASETS["supermarkets"], "supermarket"),
        load_geojson_points(DATASETS["community_clubs"], "community_club"),
        load_schools(max_school_geocode),
        load_preschools(max_preschool_geocode),
    ]
    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=["category", "name", "address", "postal_code", "lat", "lon", "source"])
    out = pd.concat(frames, ignore_index=True)
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["lat", "lon"]).drop_duplicates(["category", "name", "lat", "lon"])


@st.cache_data(ttl=86400, show_spinner=True)
def load_hdb_resale(max_records: int = 100000) -> pd.DataFrame:
    df = datastore_search(DATASETS["hdb_resale"], max_records=max_records)
    if df.empty:
        return df
    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"], errors="coerce")
        df["quarter"] = df["month"].dt.to_period("Q").astype(str)
    for c in ["resale_price", "floor_area_sqm"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["town", "flat_type", "street_name", "block", "storey_range"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.upper().str.strip()
    return df


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest(df: pd.DataFrame, lat: float, lon: float, radius_m: int, limit: int = 12) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.dropna(subset=["lat", "lon"]).copy()
    out["distance_m"] = [haversine_m(lat, lon, float(r.lat), float(r.lon)) for r in out.itertuples()]
    return out[out.distance_m <= radius_m].sort_values("distance_m").head(limit)


def build_trend(df: pd.DataFrame, town: str, flat_type: str, road_name: str = "") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if df.empty:
        return df, pd.DataFrame(), {}
    out = df.copy()
    if town != "Any":
        out = out[out.town == town]
    if flat_type != "Any":
        out = out[out.flat_type == flat_type]
    tokens = [t for t in re.sub(r"[^A-Z0-9 ]", " ", road_name.upper()).split() if len(t) >= 3 and t not in {"ROAD", "STREET", "AVENUE", "AVE", "DRIVE", "CLOSE", "LANE"}]
    if tokens and "street_name" in out:
        mask = pd.Series(False, index=out.index)
        for t in tokens:
            mask = mask | out.street_name.str.contains(t, regex=False, na=False)
        if int(mask.sum()) >= 15:
            out = out[mask]
    if out.empty:
        return out, pd.DataFrame(), {}
    q = out.dropna(subset=["quarter", "resale_price"]).groupby("quarter", as_index=False).agg(median_price=("resale_price", "median"), transactions=("resale_price", "size"))
    max_month = out["month"].max()
    last = out[out.month >= max_month - pd.DateOffset(months=12)]
    prev = out[(out.month < max_month - pd.DateOffset(months=12)) & (out.month >= max_month - pd.DateOffset(months=24))]
    last_med = float(last.resale_price.median()) if not last.empty else None
    prev_med = float(prev.resale_price.median()) if not prev.empty else None
    yoy = round((last_med - prev_med) / prev_med * 100, 1) if last_med and prev_med else None
    return out.sort_values("month", ascending=False), q, {
        "latest_quarter_median": float(q.tail(1).iloc[0].median_price) if not q.empty else None,
        "latest_quarter_transactions": int(q.tail(1).iloc[0].transactions) if not q.empty else 0,
        "last_12m_median": last_med, "prior_12m_median": prev_med, "yoy_pct": yoy,
        "sample_size": int(len(out)), "street_filtered": bool(tokens),
    }


def distance_score(d: float | None, excellent: int, good: int, maxd: int) -> float:
    if d is None:
        return 35.0
    if d <= excellent:
        return 100.0
    if d <= good:
        return 80.0
    if d <= maxd:
        return max(25.0, 80 - (d - good) / (maxd - good) * 55)
    return 10.0


def score_home(nearest_by_cat: dict[str, pd.DataFrame], trend: dict[str, Any], persona: str) -> dict[str, float]:
    def first(cat: str) -> float | None:
        df = nearest_by_cat.get(cat, pd.DataFrame())
        return None if df.empty else float(df.iloc[0].distance_m)
    daily = (distance_score(first("hawker_centre"), 500, 900, 2000) + distance_score(first("supermarket"), 500, 900, 2000)) / 2
    education = (distance_score(first("school"), 700, 1000, 2500) + distance_score(first("preschool"), 500, 800, 1800)) / 2
    transport = 65.0
    yoy = trend.get("yoy_pct")
    liquidity = trend.get("sample_size", 0)
    if yoy is None:
        price = 50.0
    elif yoy > 12:
        price = 45.0
    elif yoy > 5:
        price = 65.0
    elif yoy >= -3:
        price = 85.0
    else:
        price = 60.0
    if liquidity >= 100:
        price = min(100, price + 5)
    evidence = 75.0
    weights = PERSONA_WEIGHTS[persona]
    overall = weights["transport"] * transport + weights["daily"] * daily + weights["education"] * education + weights["price"] * price + weights["evidence"] * evidence
    return {"overall": round(overall, 1), "transport": round(transport, 1), "daily_convenience": round(daily, 1), "education": round(education, 1), "price_trend_liquidity": round(price, 1), "evidence_completeness": round(evidence, 1)}


def money(v: Any) -> str:
    return "n/a" if v is None or pd.isna(v) else f"S${float(v):,.0f}"


def dist(v: Any) -> str:
    if v is None or pd.isna(v):
        return "n/a"
    return f"{float(v):,.0f} m" if float(v) < 1000 else f"{float(v)/1000:.1f} km"


def evidence_links(query: str) -> dict[str, str]:
    domain_q = " OR ".join([f"site:{d}" for d in CREDIBLE_DOMAINS])
    return {
        "Credible-source web search": "https://www.google.com/search?q=" + urllib.parse.quote_plus(query + " " + domain_q),
        "CNA only": "https://www.google.com/search?q=" + urllib.parse.quote_plus(query + " site:channelnewsasia.com"),
        "Straits Times only": "https://www.google.com/search?q=" + urllib.parse.quote_plus(query + " site:straitstimes.com"),
        "Official gov/agency search": "https://www.google.com/search?q=" + urllib.parse.quote_plus(query + " site:gov.sg OR site:hdb.gov.sg OR site:ura.gov.sg OR site:lta.gov.sg OR site:scdf.gov.sg OR site:police.gov.sg"),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def bing_evidence_search(query: str) -> pd.DataFrame:
    key = os.getenv("BING_SEARCH_KEY")
    endpoint = os.getenv("BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
    if not key:
        return pd.DataFrame()
    allow = " OR ".join([f"site:{d}" for d in CREDIBLE_DOMAINS])
    r = requests.get(endpoint, params={"q": query + " " + allow, "count": 8, "mkt": "en-SG", "safeSearch": "Strict"}, headers={"Ocp-Apim-Subscription-Key": key}, timeout=30)
    r.raise_for_status()
    return pd.DataFrame([{"title": item.get("name", ""), "url": item.get("url", ""), "snippet": item.get("snippet", ""), "date": item.get("dateLastCrawled", "")} for item in r.json().get("webPages", {}).get("value", [])])


def fallback_brief(profile: dict[str, Any], score: dict[str, float], trend: dict[str, Any], persona: str) -> str:
    return (
        f"**Verdict for {persona}:** {profile['address']} scores **{score['overall']}/100** directionally. "
        f"The comparable HDB sample has **{trend.get('sample_size', 'n/a')} transactions**, last-12-month median "
        f"**{money(trend.get('last_12m_median'))}**, and YoY movement **{trend.get('yoy_pct', 'n/a')}%**. "
        "Verify actual walking routes, school eligibility, same-block transactions, noise, lease balance, renovation condition, and official future-development plans."
    )


def buyer_brief(profile: dict[str, Any], score: dict[str, float], trend: dict[str, Any], persona: str, nearest_by_cat: dict[str, pd.DataFrame]) -> str:
    host, token, endpoint = os.getenv("DATABRICKS_HOST"), os.getenv("DATABRICKS_TOKEN"), os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    facts = {
        "profile": profile, "persona": persona, "score": score, "trend": trend,
        "nearest": {k: (None if v.empty else {"name": v.iloc[0].get("name"), "distance_m": round(float(v.iloc[0].distance_m))}) for k, v in nearest_by_cat.items()},
    }
    prompt = "Write a concise Singapore home buyer due diligence briefing using only the supplied facts. Do not invent sensitive incidents, future plans, or advice. Include strengths, checks, and verdict.\n" + str(facts)
    if host and token:
        try:
            r = requests.post(f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 500}, timeout=45)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            return f"Databricks Model Serving fallback used: {exc}\n\n" + fallback_brief(profile, score, trend, persona)
    return fallback_brief(profile, score, trend, persona)


st.title("🏠 HomeWise SG")
st.caption("Working open-data buyer intelligence app for Singapore, designed for Databricks Apps + Lakehouse + AI.")

with st.sidebar:
    sample = st.selectbox("Try a sample", ["Custom", "308C Punggol Walk", "1 Cantonment Road", "273C Punggol Place", "1 Tanjong Pagar Plaza"])
    address = st.text_input("Address or postal code", "" if sample == "Custom" else sample)
    persona = st.selectbox("Buyer persona", list(PERSONA_WEIGHTS.keys()))
    radius = st.slider("Nearby radius", 500, 3000, 1500, 100)
    max_records = st.selectbox("HDB resale rows", [8000, 30000, 100000, 180000], index=2)
    max_school_geocode = st.slider("Max schools to geocode/cache", 50, 500, 350, 50)
    max_preschool_geocode = st.slider("Max pre-schools to geocode/cache", 100, 1500, 700, 100)
    st.caption("More geocoded school/pre-school rows = better coverage but slower first load. Cached for 24h.")

if not address:
    st.info("Enter an address or postal code to start.")
    st.stop()

try:
    profile = geocode(address)
except Exception as exc:
    st.error(f"Could not geocode with OneMap: {exc}")
    st.stop()

st.success(f"Matched: {profile['address']}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Postal", profile["postal_code"] or "n/a")
m2.metric("Road", profile["road_name"] or "n/a")
m3.metric("Latitude", f"{profile['lat']:.5f}")
m4.metric("Longitude", f"{profile['lon']:.5f}")

with st.spinner("Loading live open data..."):
    amenities = load_live_amenities(max_school_geocode, max_preschool_geocode)
    resale = load_hdb_resale(int(max_records))

nearest_by_cat = {cat: nearest(amenities[amenities.category == cat], profile["lat"], profile["lon"], radius) for cat in sorted(amenities.category.dropna().unique())}
towns = sorted(resale.town.dropna().unique().tolist()) if not resale.empty and "town" in resale else []
flats = sorted(resale.flat_type.dropna().unique().tolist()) if not resale.empty and "flat_type" in resale else []

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Live amenities map", "Price trends", "Evidence & future plans", "Databricks architecture"])

with tab3:
    st.subheader("Comparable HDB resale trend")
    a, b = st.columns(2)
    town = a.selectbox("Town", ["Any"] + towns)
    flat = b.selectbox("Flat type", ["Any"] + flats)
    filtered, quarterly, trend = build_trend(resale, town, flat, profile.get("road_name", ""))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest qtr median", money(trend.get("latest_quarter_median")))
    c2.metric("Latest qtr txns", trend.get("latest_quarter_transactions", 0))
    c3.metric("Last 12m median", money(trend.get("last_12m_median")))
    c4.metric("YoY median", "n/a" if trend.get("yoy_pct") is None else f"{trend['yoy_pct']}%")
    if not quarterly.empty:
        st.plotly_chart(px.line(quarterly, x="quarter", y="median_price", markers=True, title="Median resale price by quarter"), use_container_width=True)
    if not filtered.empty:
        cols = [c for c in ["month", "town", "flat_type", "block", "street_name", "storey_range", "floor_area_sqm", "remaining_lease", "resale_price"] if c in filtered.columns]
        st.dataframe(filtered[cols].head(50), use_container_width=True, hide_index=True)

trend_for_score = locals().get("trend", {})
score = score_home(nearest_by_cat, trend_for_score, persona)

with tab1:
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Buyer scorecard")
        st.metric("Overall", f"{score['overall']}/100")
        st.progress(score["overall"] / 100)
        st.caption(f"Persona: {persona}")
        for k, v in score.items():
            if k != "overall":
                st.write(f"**{k.replace('_', ' ').title()}**: {v}/100")
    with right:
        st.subheader("Buyer briefing")
        st.markdown(buyer_brief(profile, score, trend_for_score, persona, nearest_by_cat))
        st.warning("Prototype only. Not financial, legal, valuation, or property advice.")

with tab2:
    st.subheader("Nearby live open-data amenities")
    st.caption(f"Loaded {len(amenities):,} live amenity records. Showing records within {radius:,}m.")
    rows_for_map = []
    for cat, df in nearest_by_cat.items():
        st.markdown(f"#### {cat.replace('_', ' ').title()}")
        if df.empty:
            st.info("No result within selected radius.")
            continue
        out = df.copy()
        out["distance"] = out.distance_m.apply(dist)
        display_cols = [c for c in ["name", "distance", "address", "postal_code", "source"] if c in out.columns]
        st.dataframe(out[display_cols], use_container_width=True, hide_index=True)
        rows_for_map.append(out.head(10))
    if rows_for_map:
        map_df = pd.concat(rows_for_map, ignore_index=True)
        fig = px.scatter_mapbox(map_df, lat="lat", lon="lon", color="category", hover_name="name", hover_data={"distance_m": ":.0f", "address": True, "lat": False, "lon": False}, zoom=13, height=520)
        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Sensitive property history: credible source only")
    st.caption("No source URL = no claim. This avoids unsupported fire/suicide/crime/death/stigma statements.")
    q = f'"{profile["address"]}" (fire OR suicide OR death OR crime OR police OR SCDF OR accident) Singapore'
    evidence = bing_evidence_search(q)
    if evidence.empty:
        st.info("No search API key configured, so HomeWise shows manual credible-source search links instead of making claims.")
        for label, link in evidence_links(q).items():
            st.markdown(f"- [{label}]({link})")
    else:
        st.dataframe(evidence, use_container_width=True, hide_index=True)
    st.subheader("Future development checks")
    st.markdown("- [URA Draft Master Plan](https://www.uradraftmasterplan.gov.sg/)\n- [LTA Upcoming Projects](https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html)\n- [OneMap](https://www.onemap.gov.sg/)\n- [HDB Press Releases](https://www.hdb.gov.sg/about-us/news-and-publications/press-releases)")

with tab5:
    st.subheader("Databricks architecture")
    st.code("data.gov.sg + OneMap + official sources\n  -> Databricks notebooks\n  -> Bronze Delta raw tables\n  -> Silver cleaned tables\n  -> Gold buyer features / Genie views\n  -> Databricks App (Streamlit) + Model Serving + optional Lakebase", language="text")
    st.dataframe(pd.DataFrame([
        {"component": "Databricks App", "implementation": "app.py + app.yaml"},
        {"component": "Lakehouse ingestion", "implementation": "notebooks/01_ingest_open_data.py"},
        {"component": "Gold features", "implementation": "notebooks/02_build_features.py"},
        {"component": "Genie examples", "implementation": "notebooks/03_genie_sql_examples.sql"},
        {"component": "AI summary", "implementation": "Databricks Model Serving when configured"},
        {"component": "Memory", "implementation": "Lakebase/Postgres-ready environment variable"},
    ]), use_container_width=True, hide_index=True)
