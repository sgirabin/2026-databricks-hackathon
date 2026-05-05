# HomeWise SG — Databricks Hackathon 2026

**Track:** Social Impact / Open Data  
**Theme:** Building Intelligent Apps with Data + AI

HomeWise SG is a source-backed home buyer intelligence app for Singapore. A buyer enters an address or postal code and the app combines open data, geospatial analysis, HDB resale trends, credible-source evidence search, and Databricks-ready AI summaries to support due diligence before buying a home.

## Current status

This is now a **working open-data app**, not a dummy-only MVP:

- Live address / postal-code geocoding through OneMap public search.
- Live HDB resale data from data.gov.sg.
- Live data.gov.sg GeoJSON loaders for hawker centres, supermarkets and community clubs.
- Live data.gov.sg datastore loaders for schools and pre-schools, with OneMap geocoding where coordinates are not supplied directly.
- Persona-based buyer scorecard.
- Interactive map of nearby live amenities.
- Comparable transaction table and HDB price trend chart.
- Credible-source-only evidence workflow for sensitive property history.
- Databricks Apps, notebooks, deployment scripts and Model Serving hook.

## Buyer questions the app helps answer

As a potential buyer, I would want to know:

- How convenient is this address for daily life?
- What hawker centres, supermarkets, community clubs, schools and pre-schools are nearby?
- Which amenities are realistically within 500m, 1km or 1.5km?
- What are comparable HDB resale prices in this town / flat type / street?
- Is the price trend overheated, stable, or declining?
- Is there enough transaction liquidity to trust the comparable trend?
- Are there credible news reports about serious incidents around the block or address?
- What future URA/LTA/HDB developments may change the area?
- What should I verify manually before making an offer?

## Implemented features

- Streamlit app deployable as a Databricks App via `app.yaml`.
- OneMap geocoding for address / postal-code search.
- Live data.gov.sg loaders for HDB resale, hawker centres, schools, pre-schools, community clubs and supermarkets.
- Geocoding cache for schools and pre-schools when source records do not expose latitude/longitude.
- Distance calculation and nearest-amenity ranking.
- HDB comparable trend chart and transaction table.
- Persona-weighted buyer scorecard:
  - Balanced buyer
  - Family with young child
  - Car-free commuter
  - Investor / liquidity focused
  - Elderly parents nearby
- Sensitive-history panel that only shows credible source-backed results when a search key is configured.
- Manual credible-source search links when no search key is configured.
- Future-development evidence links for official URA/LTA/HDB sources.
- Databricks Model Serving hook for AI buyer briefing with deterministic fallback.
- Lakebase/Postgres-ready environment configuration.
- Databricks notebooks for Bronze/Silver/Gold Delta ingestion and Genie-ready SQL views.
- Local and Databricks deployment scripts.

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
export DATABRICKS_APP_NAME=homewise-sg
export GIT_REPO_URL=https://github.com/sgirabin/2026-databricks-hackathon
./scripts/deploy_databricks_git.sh
```

Or deploy from a workspace source path:

```bash
export DATABRICKS_APP_NAME=homewise-sg
export DATABRICKS_WORKSPACE_PATH=/Workspace/Users/<your-email>/homewise-sg
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

## Sensitive evidence policy

HomeWise SG does not infer or invent fire, suicide, crime, death, or stigma-related property history. The rule is:

> If there is no credible source URL, there is no claim.

If `BING_SEARCH_KEY` is not configured, the app only shows manual credible-source search links. If configured, it retrieves search results but still displays source title, URL, date and snippet instead of making unsupported claims.

## Demo flow for hackathon

1. Search a sample address such as `308C Punggol Walk`.
2. Select a persona such as `Family with young child`.
3. Review scorecard and buyer briefing.
4. Open `Live amenities map` and show the live open-data records loaded.
5. Open `Price trends`, filter by town/flat type and show trend + comparable transactions.
6. Open `Evidence & future plans` and explain the credible-source-only policy.
7. Open `Databricks architecture` and explain how the app connects to Databricks Apps, Delta tables, Genie and Model Serving.

## Disclaimer

This is a decision-support prototype for hackathon use. It is not financial, legal, valuation, or real-estate advice. Users should verify all information with official agencies, licensed property professionals, and on-site checks before purchasing.
