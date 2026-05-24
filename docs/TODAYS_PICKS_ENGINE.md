# GoAround SG - Today’s Picks Engine

This document describes the intended source-backed recommendation engine behind GoAround SG.

## Current Status

The current Databricks App entrypoint is:

```text
app_template_layout_test.py
```

That file is a static layout/debugging target. It does not yet call this engine.

The reusable engine already exists in:

```text
src/goaround/
```

Older app files such as `app_picks.py`, `app_final.py`, `app_clean.py`, and the `app_template_*.py` variants show previous attempts to wire this engine into Streamlit. Treat them as implementation references unless `app.yaml` points to them.

## Product Position

GoAround SG is a local discovery assistant for useful things around where people live, work, study, or visit.

The main experience is:

```text
Today’s Picks Near You
```

It turns open data, live APIs, source registries, user context, and AI into ranked cards.

## Core Modules

```text
src/goaround/models.py       # UserContext, PickCard, RankedPick
src/goaround/ranking.py      # ranking algorithm and explainability
src/goaround/seed_data.py    # source-backed seed cards and local search cards
src/goaround/business.py     # business promotion card creation
src/goaround/agent.py        # Ask GoAround / Databricks Model Serving helper
src/goaround/lakehouse.py    # optional Databricks SQL Gold-card loader
```

## Card Types

```text
deal
food
event
transport
local_update
plan
```

Each card should include:

```text
title
description
category
source_name
source_url
distance_m when available
why_shown
actions such as Save / Share / Remind / Open source
```

Important rule:

```text
No source URL = no claim.
```

## Ranking Logic

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

## Source-Backed Candidate Cards

Candidate cards can come from:

- data.gov.sg open-data places such as hawker centres, supermarkets, and community clubs
- data.gov.sg weather context
- OneMap geocoding / reverse geocoding
- LTA DataMall bus stops and arrivals when configured
- official supermarket, mall, community, NLB, ActiveSG, URA, and LTA source registries
- business-submitted promotion cards with source URLs
- Databricks SQL `gold_candidate_cards` when configured

## Ask GoAround

`src/goaround/agent.py` supports two modes:

- Databricks Model Serving when `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are configured
- local deterministic fallback when Databricks credentials are absent

Both modes are expected to answer from supplied source-backed cards only.

## Databricks Architecture

```text
Open data + live APIs + source registries
  -> Databricks Jobs / Workflows
  -> Bronze raw Delta tables
  -> Silver cleaned/geocoded local entities
  -> Gold candidate cards / Today’s Picks
  -> Databricks App: GoAround SG
  -> Model Serving: Ask GoAround
  -> Genie: local demand analytics
  -> Lakebase: saved areas, reminders, business promotions, interests
```

## Next Integration Step

Once `app_template_layout_test.py` is visually stable, wire it to:

- `source_registry_cards()`
- `area_anchor_cards()`
- `rank_cards()`
- `create_business_promo_card()`
- `answer_with_databricks()`
- optionally `load_gold_candidate_cards()`

That will turn the static layout into the live source-backed Today’s Picks experience.
