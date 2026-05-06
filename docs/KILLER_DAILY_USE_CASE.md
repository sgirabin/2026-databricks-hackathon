# GoAround SG - Killer daily use case refactor

Branch:

```text
feature/killer-daily-use-case
```

## Why this branch exists

The previous app had many useful features, but the experience was too broad. This branch refocuses GoAround SG around one daily habit:

> Today around my block.

The goal is to make the product feel like something a resident can open every morning or before leaving home.

## New main entrypoint

```text
app_daily.py
```

`app.yaml` now deploys this file in this branch.

The broader `app_goaround.py` remains in the repo for reference, but the demo app should use the focused daily version.

## Simplified information architecture

Instead of many tabs, the app now uses five:

1. **Today**
   - daily neighbourhood briefing
   - everyday score
   - weather
   - transport summary
   - food/grocery/community cards
   - map around block

2. **Transport**
   - nearby bus stops
   - live bus arrivals when `LTA_ACCOUNT_KEY` is configured
   - favourite bus stop session memory

3. **Deals & Events**
   - source-backed promotion links
   - source-backed event links
   - optional Bing Search results when `BING_SEARCH_KEY` is configured
   - quick meal plan using nearby food/grocery data

4. **Ask GoAround**
   - natural-language daily neighbourhood assistant
   - Databricks Model Serving when configured
   - grounded fallback otherwise

5. **More**
   - buyer / tenant mode hidden under an expander
   - Databricks architecture hidden under an expander

## What clutter was removed from the primary UX

The following are no longer top-level tabs:

- Meal planner
- Weekend planner
- Jogging route planner
- News & safety
- Buyer mode
- Databricks architecture

They are either folded into Today / Deals & Events / Ask, or moved to More.

## The habit loop

```text
Save my block
  -> Open Today
  -> Check transport/weather/food/grocery/events
  -> Ask GoAround if needed
  -> Save favourite bus stop/interests
  -> Return tomorrow
```

## Databricks story

This branch still supports the Databricks hackathon story:

- **Databricks Apps**: deploys `app_daily.py`
- **Lakehouse / Delta**: open-data ingestion notebooks remain available
- **Genie**: natural-language neighbourhood questions
- **Model Serving**: Ask GoAround and daily briefing responses
- **Lakebase**: planned persistence for saved block, favourite bus stop, interests and alerts
- **Jobs / Workflows**: planned daily refresh of deals, events, transport snapshots and local updates

## Environment variables for strongest demo

```dotenv
LTA_ACCOUNT_KEY=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
LAKEBASE_DATABASE_URL=
```

The app can still run without these, but transport arrivals, source-backed search and rich AI answers require the relevant keys.

## Recommended demo

1. Search `308C Punggol Walk`.
2. Click **Save my block**.
3. Show **Today**: daily cards and map.
4. Show **Transport**: bus stops / arrivals if LTA key is configured.
5. Show **Deals & Events**: source-backed promotions/events and quick meal plan.
6. Show **Ask GoAround**: ask “What is useful around my block today?”
7. Open **More > Databricks usage** to explain the platform architecture.
