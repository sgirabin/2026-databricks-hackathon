# GoAround SG - Today’s Picks Engine

Branch:

```text
feature/todays-picks-engine
```

## Product position

GoAround SG is an AI-powered local lobang feed for useful things around where people live, work, study or visit.

The main experience is:

```text
Today’s Picks Near You
```

It turns open data, live APIs, source-backed promotion/event registries, user context and AI into ranked cards.

## Why this is stronger

The product is no longer only a neighbourhood dashboard or home-buyer app. It is a local discovery feed that can drive recurring usage across different users:

- residents checking food, grocery, events and local updates
- workers/students checking lunch, coffee and after-work options
- tourists/visitors asking for short local plans
- businesses submitting hyperlocal promotions
- potential movers using buyer/tenant mode later

## Clean code structure

```text
app_picks.py                    # Streamlit app, thin UI layer
src/goaround/models.py          # UserContext, PickCard, RankedPick
src/goaround/ranking.py         # ranking algorithm and explainability
src/goaround/seed_data.py       # source-backed seed cards and local search cards
src/goaround/business.py        # business promotion card creation
src/goaround/agent.py           # Ask GoAround / Databricks Model Serving helper
```

## Main tabs

```text
Today’s Picks
Deals
Things To Do
Ask GoAround
My Area
Business Demo
Data & Databricks
```

## Card types

```text
deal
food
event
transport
local_update
plan
```

Each card includes:

```text
title
description
category
source_name
source_url
distance_m
why_shown
actions: Save / Share / Remind / Open source
```

Important rule:

```text
No source URL = no claim.
```

## Ranking logic

Cards are ranked using:

- distance to selected area
- user interests
- user mode: resident, worker/student, visitor, considering moving here
- time of day: morning, lunch, evening, weekend
- weather context
- source reliability
- freshness
- business-submitted status

The ranking engine also generates a `why_shown` explanation for each card.

## Open data usage

The app uses open data and public APIs as a neighbourhood knowledge layer:

- data.gov.sg hawker centre / food anchors
- data.gov.sg supermarket anchors
- data.gov.sg community club anchors
- data.gov.sg weather API
- OneMap geocoding
- LTA DataMall bus stops / arrivals when configured
- source-backed event and promotion registries

## Databricks usage

This is the intended Databricks architecture:

```text
Open data + live APIs + source registries
  -> Databricks Jobs / Workflows
  -> Bronze raw Delta tables
  -> Silver cleaned/geocoded local entities
  -> Gold today_picks, user_area_profile, card_interactions
  -> Databricks App: GoAround SG
  -> Model Serving: Ask GoAround
  -> Genie: local demand analytics
  -> Lakebase: saved areas, reminders, business promotions
```

## Hackathon demo flow

1. Open GoAround SG.
2. Select mode: `Resident` or `Visitor`.
3. Search `308C Punggol Walk`, `83 Punggol Central`, `Chinatown MRT`, or `Orchard Road`.
4. Select interests: cheap food, grocery, event, tourist, rainy day.
5. Show Today’s Picks.
6. Show why cards are ranked.
7. Save/share/remind a card.
8. Open Business Demo and submit a local promotion.
9. Return to Today’s Picks and show the card can appear if relevant.
10. Ask GoAround: `I am visiting this area for 2 hours. What should I do?`
11. Open Data & Databricks and explain the platform story.

## Environment variables

```dotenv
DATA_GOV_API_KEY=
LTA_ACCOUNT_KEY=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
LAKEBASE_DATABASE_URL=
```

The app can run without these keys, but the strongest demo uses:

- LTA key for bus cards
- Databricks endpoint for Ask GoAround
- Lakebase later for persistent memory/business submissions

## Business angle

Businesses can submit source-backed local promotions with:

- business name
- title
- category
- source URL
- location
- valid date
- target tags

In production, the same flow should persist to Lakebase and be moderated by an AI validation workflow before appearing in Today’s Picks.
