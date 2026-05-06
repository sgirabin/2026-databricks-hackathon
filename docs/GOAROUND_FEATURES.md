# GoAround SG - implemented resident-first features

This document explains the resident-first feature expansion added for the Databricks hackathon.

## Main app entrypoint

Databricks App now runs:

```text
app_goaround.py
```

`app.yaml` has been updated to point to this file.

The older `app.py` is kept as backup/reference for the original home-buyer-focused prototype.

## Implemented resident-first features

### 1. Today dashboard

- Resident enters/saves a block, address or postal code.
- App geocodes through OneMap.
- App loads nearby open-data amenities.
- App shows a daily neighbourhood briefing.
- App shows neighbourhood score based on:
  - transport
  - daily convenience
  - family fit
  - environment/safety
  - evidence completeness

### 2. Transport tab

- Loads nearby bus stops from LTA DataMall when `LTA_ACCOUNT_KEY` is configured.
- Retrieves live bus arrivals from LTA DataMall BusArrival API.
- Shows nearest bus stops and bus arrival timing.
- If no key is configured, the tab explains what environment variable is required.

### 3. Meal planner

- Suggests practical meal options based on nearby hawker centres and supermarkets.
- Supports preferences such as budget-first, family-friendly, vegetarian-friendly, healthier choice, etc.
- Uses Databricks Model Serving when configured.
- Falls back to deterministic source-aware recommendations.
- Shows official promotion source links for supermarkets and malls.

### 4. Weekend planner

- Builds a weekend plan using nearby amenities, community clubs, weather and user interests.
- Shows official source links for OnePA, NLB, ActiveSG, PA, HDB, LTA and URA.
- Uses Bing Search if `BING_SEARCH_KEY` is configured; otherwise shows source links only.

### 5. Jogging route planner

- Creates an approximate open-data waypoint loop from the resident's block to nearby places.
- Shows the route on a map.
- Includes safety disclaimer because it is not turn-by-turn navigation.

### 6. Promotions and community events

- Provides source-backed promotion/event discovery architecture.
- Uses official source registry and optional Bing Search.
- Does not invent promotions or events.

### 7. News, safety and environment

- Loads weather and rainfall information from data.gov.sg APIs.
- Attempts to load dengue clusters from data.gov.sg.
- Uses credible-source-only search workflow for local news/safety updates.
- Follows the rule: no source URL = no claim.

### 8. Buyer / tenant mode

- Keeps HDB resale trend and comparable transactions as a secondary mode.
- This supports residents, tenants and buyers who want to evaluate an area.

### 9. Ask GoAround / Databricks tab

- Shows Databricks architecture.
- Provides example Genie / AI questions.
- Includes an Ask GoAround input box.
- Uses Databricks Model Serving when configured; otherwise explains fallback.

## Data dependencies

| Feature | Source | Needs key? |
|---|---|---|
| Address geocoding | OneMap public search | No for current endpoint |
| Hawker centres | data.gov.sg / NEA | No, API key recommended |
| Supermarkets | data.gov.sg / SFA | No, API key recommended |
| Community clubs | data.gov.sg / PA | No, API key recommended |
| Schools | data.gov.sg / MOE + OneMap geocode | No, API key recommended |
| Pre-schools | data.gov.sg / ECDA + OneMap geocode | No, API key recommended |
| Weather forecast | data.gov.sg | No |
| Rainfall | data.gov.sg | No |
| Dengue clusters | data.gov.sg / NEA | No, API key recommended |
| Bus stops | LTA DataMall | Yes, `LTA_ACCOUNT_KEY` |
| Bus arrivals | LTA DataMall | Yes, `LTA_ACCOUNT_KEY` |
| Promotions | Official source registry + optional Bing Search | Bing key optional |
| Community events | Official source registry + optional Bing Search | Bing key optional |
| Local news/safety | Credible domains + optional Bing Search | Bing key optional |
| AI briefing/planners | Databricks Model Serving | Databricks token/endpoint optional |
| Saved block memory | Streamlit session now; Lakebase planned | Lakebase URL optional |

## Required environment variables for strongest demo

```dotenv
LTA_ACCOUNT_KEY=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
LAKEBASE_DATABASE_URL=
```

Minimum app demo can run without these, but transport arrivals, automatic promotion/event discovery and Databricks-generated briefings require the relevant keys.

## Recommended demo flow

1. Search `308C Punggol Walk`.
2. Show `Today` tab as the resident daily briefing.
3. Show `Transport` tab and explain LTA DataMall integration.
4. Show `Meals` tab for meal planning around hawker/supermarket data.
5. Show `Weekend` tab for resident activity planning.
6. Show `Jogging` tab for lifestyle use case.
7. Show `Promos & events` and explain source-backed discovery.
8. Show `News & safety` and explain credible-source policy.
9. Show `Buyer mode` as secondary use case.
10. Show `Databricks` tab to explain Apps, Lakehouse, Genie, Model Serving and Lakebase.
