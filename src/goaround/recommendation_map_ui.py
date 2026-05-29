from __future__ import annotations

import re
import urllib.parse
from typing import Any, Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from src.goaround.models import RankedPick, UserContext


RECOMMENDATION_INTENT_WORDS = (
    "recommend", "where", "eat", "food", "lunch", "dinner", "coffee", "deal",
    "go", "visit", "do", "kid", "family", "weekend", "near", "nearby",
)


def should_show_recommendation_map(prompt: str, ranked_items: Iterable[RankedPick]) -> bool:
    """Return True when a chat prompt is likely asking for mappable picks."""

    text = prompt.lower()
    has_intent = any(word in text for word in RECOMMENDATION_INTENT_WORDS)
    has_mappable = any(
        item.card.lat is not None and item.card.lon is not None
        for item in ranked_items
    )
    return has_intent and has_mappable


def _directions_url(lat: float, lon: float, name: str | None = None) -> str:
    query = f"{name or 'Destination'} {lat:.6f},{lon:.6f}"
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(query)


def _safe_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value)


def _distance_label(distance_m: float | None) -> str:
    if distance_m is None:
        return "distance n/a"
    value = float(distance_m)
    return f"{value:,.0f} m" if value < 1000 else f"{value / 1000:.1f} km"


def _mappable_ranked_items(ranked_items: Iterable[RankedPick], limit: int = 3) -> list[RankedPick]:
    picked: list[RankedPick] = []
    seen: set[str] = set()

    for item in ranked_items:
        card = item.card
        if card.lat is None or card.lon is None:
            continue
        key = f"{round(float(card.lat), 5)}:{round(float(card.lon), 5)}:{card.title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        picked.append(item)
        if len(picked) >= limit:
            break

    return picked


def recommendation_payload(ranked_items: Iterable[RankedPick], limit: int = 3) -> list[dict[str, Any]]:
    """Build a serialisable top-N recommendation payload for chat messages."""

    payload: list[dict[str, Any]] = []
    for idx, item in enumerate(_mappable_ranked_items(ranked_items, limit), start=1):
        card = item.card
        lat = float(card.lat) if card.lat is not None else None
        lon = float(card.lon) if card.lon is not None else None
        if lat is None or lon is None:
            continue

        payload.append({
            "pin": str(idx),
            "name": card.title,
            "category": card.category.title(),
            "lat": lat,
            "lon": lon,
            "distance_m": item.distance_m,
            "score": item.score,
            "reason": item.why_shown,
            "source_name": card.source_name,
            "source_url": card.source_url,
            "directions_url": _directions_url(lat, lon, card.location_name or card.title),
            "description": card.description,
        })

    return payload


def render_recommendation_map_block(
    ranked_items: Iterable[RankedPick],
    context: UserContext,
    *,
    limit: int = 3,
    key_prefix: str = "chat-recs",
) -> None:
    """Render a compact chat-safe map preview with up to three recommendation cards.

    The chat bubble remains text-first. The map is a small preview, details are
    progressively disclosed, and the block never renders more than three cards.
    """

    points = recommendation_payload(ranked_items, limit)
    if not points:
        return

    shown_count = len(points)
    plural = "s" if shown_count != 1 else ""
    st.caption(f"Map preview · top {shown_count} mappable recommendation{plural}")

    map_rows = [
        {
            "pin": "You",
            "name": "You are here",
            "lat": context.lat,
            "lon": context.lon,
            "category": "Current area",
        }
    ]
    map_rows.extend(points)
    map_df = pd.DataFrame(map_rows)

    fig = px.scatter_mapbox(
        map_df,
        lat="lat",
        lon="lon",
        color="category",
        text="pin",
        hover_name="name",
        hover_data={"lat": False, "lon": False, "pin": False, "category": True},
        zoom=13,
        height=280,
    )
    fig.update_traces(marker_size=15, textposition="top center")
    fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    cols = st.columns(min(3, shown_count))
    for point, col in zip(points, cols):
        card_key = _safe_key(f"{key_prefix}-{point['pin']}-{point['name']}")
        with col:
            with st.container(border=True):
                st.markdown(f"**{point['pin']}. {point['name']}**")
                st.caption(f"{point['category']} · {_distance_label(point['distance_m'])} · score {point['score']:.2f}")
                st.write(point["description"])
                with st.expander("Why this pick"):
                    st.write(point["reason"])
                    st.caption(f"Source: {point['source_name']}")
                b1, b2 = st.columns(2)
                b1.link_button("Directions", point["directions_url"], key=f"dir-{card_key}")
                b2.link_button("Source", point["source_url"], key=f"source-{card_key}")

    if shown_count >= limit:
        source_query = urllib.parse.quote_plus(f"{context.address} recommendations near me")
        st.link_button(
            "Open larger map search",
            f"https://www.google.com/maps/search/{source_query}",
            key=f"larger-map-{_safe_key(key_prefix)}",
        )
