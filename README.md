# GoAround SG - Databricks Hackathon 2026

**Track:** Social Impact / Open Data  
**Theme:** Building Intelligent Apps with Data + AI

GoAround SG is a Singapore local discovery assistant for residents, workers, students, visitors, and nearby businesses. The product direction is a daily "what is useful around me today?" experience: food, grocery deals, events, weather-aware ideas, transport context, local updates, and business promotions, backed by open data and source links.

The current branch is in **debugging / UI polishing mode**. The deployed app is intentionally a mostly static Streamlit layout so layout, navigation, spacing, browser geolocation, and Databricks App rendering issues can be fixed before reconnecting the full data/ranking engine.

## Current Entry Point

Databricks Apps runs the file configured in `app.yaml`:

```bash
streamlit run app_template_layout_test.py
```

`app_template_layout_test.py` is the current layout target. It renders:

- a custom left navigation shell
- `GoAround Today`
- `Business Promotion`
- `What is GoAround?`
- browser geolocation when permission is granted
- nearest known-area labeling for detected coordinates
- live weather and temperature from data.gov.sg with a fallback
- static Today’s Picks cards and a static business promotion form preview

The static cards and business form are placeholders. The source-backed ranking engine already exists in `src/goaround`, but it is not wired into `app_template_layout_test.py` yet.

## Product Promise

> Open GoAround SG and quickly discover useful, source-backed things around your current area: food, deals, events, weather-aware options, local context, and business promotions.

The original home-buyer / tenant evaluation idea is now secondary. The main product is a daily local discovery feed that can support repeat usage.

## Current Repository Shape

```text
app_template_layout_test.py   # current Databricks App entrypoint and layout debugging target
app.yaml                      # Databricks App command
src/goaround/                 # reusable Today’s Picks engine and AI helper modules
databricks/                   # Lakehouse setup script for open-data Delta tables
notebooks/                    # earlier ingestion / feature / Genie examples
config/data_sources.yml       # source catalogue
docs/TODAYS_PICKS_ENGINE.md   # current architecture note
```

There are several older `app_*.py` and `app_template_*.py` files in the repository. Treat them as prototypes/reference unless `app.yaml` points to them.

## Implemented Engine Pieces

The reusable engine is in `src/goaround`:

- `models.py`: `UserContext`, `PickCard`, `RankedPick`
- `ranking.py`: distance, interest, time-of-day, weather, freshness, source reliability, and business-promotion ranking
- `seed_data.py`: official/source-backed seed cards and area search cards
- `business.py`: source-backed business promotion card creation
- `agent.py`: Ask GoAround helper using Databricks Model Serving when configured, with a safe local fallback
- `lakehouse.py`: optional Databricks SQL loader for `gold_candidate_cards`

Important rule:

> No source URL = no claim.

The app should not invent promotions, incidents, prices, events, timings, or official claims without a source URL.

## Databricks Story

| Databricks capability | Intended GoAround SG usage |
|---|---|
| Databricks Apps | Host the Streamlit intelligent app |
| Lakehouse / Delta | Store Bronze, Silver, and Gold local discovery data |
| Databricks SQL | Serve Gold candidate cards to the app |
| Model Serving | Power Ask GoAround responses from source-backed context |
| Genie | Natural-language analytics over local demand, cards, and interactions |
| Lakebase | Persist saved areas, interests, reminders, business submissions, and user memory |
| Jobs / Workflows | Refresh open data, source registries, and candidate cards |

The direct public-API path is still useful for demos, but the stronger hackathon architecture is:

```text
Open data + live APIs + source registries
  -> Databricks Jobs / Workflows
  -> Bronze raw Delta tables
  -> Silver cleaned/geocoded local entities
  -> Gold candidate cards / Today’s Picks
  -> Databricks App + Ask GoAround
```

## Quick Start Locally

Use Python 3.10 or newer. On this machine, Python 3.9.7 is not suitable because current Streamlit versions exclude it.

```bash
/usr/local/bin/python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app_template_layout_test.py
```

If you want to run an older prototype, run it explicitly, for example:

```bash
streamlit run app_picks.py
```

## Configuration

The current layout target can run without environment variables. Stronger engine-backed demos may use:

```dotenv
DATA_GOV_API_KEY=
LTA_ACCOUNT_KEY=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
DATABRICKS_SERVER_HOSTNAME=
DATABRICKS_HTTP_PATH=
USE_DATABRICKS_SQL=false
GOAROUND_CATALOG=main
GOAROUND_SCHEMA=goaround_sg
LAKEBASE_DATABASE_URL=
```

## Data Sources

The source catalogue is in `config/data_sources.yml`. Relevant sources include:

- data.gov.sg weather APIs
- data.gov.sg hawker centre, supermarket, and community club datasets
- OneMap geocoding / reverse geocoding
- LTA DataMall bus stops and bus arrivals when configured
- official mall, supermarket, community, URA, HDB, LTA, and NLB source links

Some older files still reference HDB resale, schools, pre-schools, buyer mode, and wider neighbourhood intelligence features. Those are historical/reference features, not the current active layout target.

## Debugging Focus

Current work should usually start from:

```text
app_template_layout_test.py
```

Likely next implementation step after layout debugging:

```text
wire app_template_layout_test.py to src/goaround ranking, source cards, business card creation, and Ask GoAround
```

## Verification

Basic checks:

```bash
python -m py_compile app_template_layout_test.py src/goaround/*.py
python -m pytest
```

There are currently no test files, so `pytest` reports that it collected 0 items.

## Disclaimer

GoAround SG is a hackathon prototype. It is not financial, legal, safety, transport, valuation, or official government advice. Users should verify important information with the original source.
