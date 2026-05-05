# HomeWise SG — Databricks Hackathon 2026

**Track:** Social Impact / Open Data  
**Theme:** Building Intelligent Apps with Data + AI

HomeWise SG is a source-backed home buyer intelligence app for Singapore. A buyer enters an address or postal code and the app combines open data, geospatial analysis, HDB resale trends, credible-source evidence search, and Databricks-ready AI summaries to support due diligence before buying a home.

## Buyer questions the app helps answer

As a potential buyer, I would want to know:

- How convenient is this address for daily life?
- What hawker centres, markets, supermarkets, community clubs, malls, public facilities and transport options are nearby?
- Which schools and pre-schools are close enough to matter?
- What are comparable HDB resale prices in this town / flat type / street?
- Is the price trend overheated, stable, or declining?
- Are there credible news reports about serious incidents around the block or address?
- What future URA/LTA/HDB developments may change the area?
- What should I verify manually before making an offer?

## MVP features implemented

- Streamlit app deployable as a Databricks App via `app.yaml`.
- OneMap geocoding for address / postal-code search.
- data.gov.sg loaders for HDB resale, HDB resale price index, hawker centres, schools, pre-schools, community clubs and supermarkets.
- Distance calculation and nearest-amenity ranking.
- HDB comparable trend chart and transaction table.
- Transparent buyer scorecard.
- Sensitive-history panel that only shows credible source-backed results when a search key is configured.
- Future-development evidence hooks for official URA/LTA/HDB sources.
- Databricks model-serving hook for AI buyer briefing with deterministic fallback.
- Lakebase/Postgres-ready memory for saved searches.
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
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
LAKEBASE_DATABASE_URL=
```

## Data sources

The data catalogue is in `config/data_sources.yml`. Main sources include HDB resale transactions, HDB resale price index, NEA hawker centres, MOE schools, ECDA centres, PA community clubs, SFA supermarkets, OneMap, URA planning pages and LTA project pages.

## Sensitive evidence policy

HomeWise SG does not infer or invent fire, suicide, crime, death, or stigma-related property history. The rule is:

> If there is no credible source URL, there is no claim.

This is a hackathon prototype and is not financial, legal, valuation, or property advice.
