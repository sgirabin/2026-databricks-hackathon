# GoAround SG — Databricks Hackathon 2026

**Track:** Social Impact / Open Data  
**Theme:** Building Intelligent Apps with Data + AI

GoAround SG is a Databricks-powered daily neighbourhood intelligence app for Singapore residents. A resident saves their block, postal code, or address, and the app turns open data, location intelligence, AI summaries, community updates, transport context, promotions, and credible-source evidence into a useful daily view of what is happening around them.

The original home-buyer scenario remains as one secondary use case: people who are considering living in a block can use the same neighbourhood intelligence to evaluate the area. The core product, however, is for **residents who stay there and want useful local information every day**.

## Product promise

> Save your block once. Get a daily AI-powered view of useful things around you — transport, food, groceries, promotions, events, news, amenities, and future changes.

## Why this fits the hackathon

The hackathon asks teams to go beyond dashboards and create intelligent apps that combine data, AI, analytics, and automation into experiences people can use every day. GoAround SG fits this because residents can use it repeatedly to answer:

- What is useful around my block today?
- Any supermarket, hawker, mall, or food promotions nearby?
- What community events are happening around my estate?
- Which nearby bus stops and MRT options are useful?
- Any credible local news, incidents, road closures, or town council updates?
- What public facilities are nearby?
- What future developments may affect where I live?
- If I am considering moving here, what should I know about this block and neighbourhood?

## Current working status

This is now a working open-data app foundation:

- Live address / postal-code geocoding through OneMap public search.
- Live HDB resale data from data.gov.sg for buyer / area-value mode.
- Live data.gov.sg GeoJSON loaders for hawker centres, supermarkets and community clubs.
- Live data.gov.sg datastore loaders for schools and pre-schools, with OneMap geocoding where coordinates are not supplied directly.
- Interactive map of nearby live amenities.
- Resident / buyer persona scoring foundation.
- Comparable HDB transaction table and price trend chart for optional home-buyer mode.
- Credible-source-only evidence workflow for local news / sensitive property history.
- Databricks Apps, notebooks, deployment scripts and Model Serving hook.

## Target users

### Primary user: resident

A resident uses GoAround SG as a daily neighbourhood companion:

- daily local briefing around their block
- food, groceries, hawker, mall, and community promotions
- nearby bus arrival and public transport convenience
- events around the estate
- useful facilities and services nearby
- credible local news and safety updates
- future development or estate-upgrading context

### Secondary user: potential home buyer / tenant

A buyer or tenant uses GoAround SG to evaluate whether a block or neighbourhood fits their lifestyle:

- convenience score
- nearby amenities
- school / pre-school proximity
- HDB resale trends and comparable transactions
- local news and future development evidence

## Implemented features

- Streamlit app deployable as a Databricks App via `app.yaml`.
- OneMap geocoding for address / postal-code search.
- Live data.gov.sg loaders for HDB resale, hawker centres, schools, pre-schools, community clubs and supermarkets.
- Geocoding cache for schools and pre-schools when source records do not expose latitude/longitude.
- Distance calculation and nearest-amenity ranking.
- Live neighbourhood map.
- HDB comparable trend chart and transaction table for buyer mode.
- Persona-weighted scoring foundation:
  - Balanced resident
  - Family with young child
  - Car-free commuter
  - Investor / buyer mode
  - Elderly parents nearby
- Local news / sensitive-history panel that only shows credible source-backed results when a search key is configured.
- Manual credible-source search links when no search key is configured.
- Future-development evidence links for official URA/LTA/HDB sources.
- Databricks Model Serving hook for AI neighbourhood briefing with deterministic fallback.
- Lakebase/Postgres-ready environment configuration for saved blocks, preferences, watchlists and alerts.
- Databricks notebooks for Bronze/Silver/Gold Delta ingestion and Genie-ready SQL views.
- Local and Databricks deployment scripts.

## Databricks usage

| Databricks capability | How GoAround SG uses it |
|---|---|
| Databricks Apps | Deploys the resident-facing Streamlit intelligent app |
| Lakehouse / Delta | Stores open data, cleaned location tables, and Gold neighbourhood features |
| Genie | Enables natural-language questions over neighbourhood and price datasets |
| Model Serving | Generates AI neighbourhood briefings and recommendations |
| Lakebase | Planned memory layer for saved blocks, resident preferences, watchlists and alert settings |
| Jobs / workflows | Planned automation for daily data refresh, event ingestion and alert generation |

## Quick start locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

The first run may be slower because school/pre-school records are geocoded and cached for 24 hours.

## Databricks App deployment

```bash
export DATABRICKS_APP_NAME=goaround-sg
export GIT_REPO_URL=https://github.com/sgirabin/2026-databricks-hackathon
./scripts/deploy_databricks_git.sh
```

Or deploy from a workspace source path:

```bash
export DATABRICKS_APP_NAME=goaround-sg
export DATABRICKS_WORKSPACE_PATH=/Workspace/Users/<your-email>/goaround-sg
./scripts/deploy_databricks_workspace.sh
```

## Configuration

Copy `.env.example` to `.env` and update later:

```dotenv
DATA_GOV_API_KEY=
ONEMAP_EMAIL=
ONEMAP_PASSWORD=
ONEMAP_ACCESS_TOKEN=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
DATABRICKS_SERVER_HOSTNAME=
DATABRICKS_HTTP_PATH=
DATABRICKS_SQL_ACCESS_TOKEN=
USE_DATABRICKS_SQL=false
LAKEBASE_DATABASE_URL=
```

## Data sources

The data catalogue is in `config/data_sources.yml`. Main sources include HDB resale transactions, HDB resale price index, NEA hawker centres, MOE schools, ECDA centres, PA community clubs, SFA supermarkets, OneMap, URA planning pages and LTA project pages.

Future promotion/event sources can include mall websites, supermarket promotion pages, PA/community event pages, town council updates, and curated user-submitted sources.

## Sensitive evidence policy

GoAround SG does not infer or invent fire, suicide, crime, death, or stigma-related local history. The rule is:

> If there is no credible source URL, there is no claim.

If `BING_SEARCH_KEY` is not configured, the app only shows manual credible-source search links. If configured, it retrieves search results but still displays source title, URL, date and snippet instead of making unsupported claims.

## Demo flow for hackathon

1. Search a sample address such as `308C Punggol Walk`.
2. Select a resident persona such as `Family with young child` or `Car-free commuter`.
3. Review the neighbourhood briefing and scorecard.
4. Open `Live amenities map` and show the live open-data records loaded.
5. Explain daily-use modules: promotions, bus arrival, local events and news can be layered on the same block-based profile.
6. Open `Price trends` as secondary buyer/tenant mode.
7. Open `Evidence & future plans` and explain the credible-source-only policy.
8. Open `Databricks architecture` and explain how the app connects to Databricks Apps, Delta tables, Genie, Model Serving and Lakebase.

## Disclaimer

This is a decision-support prototype for hackathon use. It is not financial, legal, valuation, transport, or safety advice. Users should verify important information with official agencies and service providers.
