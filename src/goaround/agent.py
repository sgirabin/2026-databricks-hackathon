from __future__ import annotations

import os
from typing import Any

import requests

from .models import RankedPick, UserContext


def build_agent_facts(context: UserContext, ranked: list[RankedPick]) -> dict[str, Any]:
    return {
        "mode": context.mode,
        "address": context.address,
        "radius_m": context.radius_m,
        "interests": list(context.interests),
        "time_of_day": context.time_of_day,
        "weather": context.weather,
        "today_picks": [
            {
                "title": item.card.title,
                "type": item.card.card_type,
                "category": item.card.category,
                "description": item.card.description,
                "source": item.card.source_name,
                "source_url": item.card.source_url,
                "distance_m": None if item.distance_m is None else round(item.distance_m),
                "why_shown": item.why_shown,
            }
            for item in ranked[:8]
        ],
    }


def _dist(item: RankedPick) -> str:
    if item.distance_m is None:
        return ""
    return f" ({item.distance_m:.0f}m away)"


def _format_items(items: list[RankedPick], intro: str) -> str:
    if not items:
        return "I could not find a strong source-backed match for that question in the current area. Try widening the radius or checking the Deals / Things To Do tabs."
    lines = [intro]
    for item in items[:4]:
        card = item.card
        lines.append(f"- **{card.title}**{_dist(item)} — {card.description} Source: {card.source_name}.")
    lines.append("\nPlease open the source before acting. I will not invent prices, events, or promotions without a source URL.")
    return "\n".join(lines)


def fallback_answer(question: str, context: UserContext, ranked: list[RankedPick], fallback: str) -> str:
    """Rule-based free-query fallback when Databricks Model Serving is not configured.

    This keeps the demo useful without an endpoint. It routes common user intents
    to the relevant source-backed cards instead of blindly returning the top card.
    """

    if not ranked:
        return fallback

    q = question.lower().strip()

    food_words = {"eat", "food", "lunch", "dinner", "breakfast", "meal", "hungry", "hawker", "restaurant", "coffee"}
    deal_words = {"deal", "promo", "promotion", "discount", "cheap", "lobang", "offer", "grocery", "supermarket"}
    event_words = {"event", "activity", "activities", "weekend", "kid", "kids", "child", "children", "family", "do"}
    rain_words = {"rain", "rainy", "indoor", "weather", "shower", "showers"}
    visitor_words = {"visit", "visiting", "tourist", "visitor", "2 hours", "two hours", "itinerary", "plan", "explore"}

    def matches(item: RankedPick, words: set[str], types: set[str] | None = None) -> bool:
        card = item.card
        haystack = " ".join([
            card.card_type,
            card.category,
            card.title,
            card.description,
            " ".join(card.tags),
        ]).lower()
        type_ok = True if not types else card.card_type in types or card.category.lower() in types
        return type_ok and any(w in haystack for w in words)

    if any(w in q for w in food_words):
        items = [x for x in ranked if matches(x, food_words | {"cheap food", "local food"}, {"food", "deal"})]
        return _format_items(items, f"For food around **{context.address}**, I would start with these source-backed options:")

    if any(w in q for w in deal_words):
        items = [x for x in ranked if matches(x, deal_words, {"deal", "food"})]
        return _format_items(items, f"For deals or lobang near **{context.address}**, check these first:")

    if any(w in q for w in event_words):
        items = [x for x in ranked if matches(x, event_words | {"things to do", "community"}, {"event", "plan", "local_update"})]
        return _format_items(items, f"For things to do near **{context.address}**, these are the most relevant source-backed picks:")

    if any(w in q for w in rain_words):
        items = [x for x in ranked if matches(x, rain_words | {"rainy day", "indoor", "mall"}, {"plan", "event", "local_update", "deal"})]
        return _format_items(items, f"For rainy-day or weather-aware options near **{context.address}**, consider:")

    if any(w in q for w in visitor_words) or context.mode.lower() == "visitor":
        items = [x for x in ranked if matches(x, visitor_words | {"tourist", "local food", "things to do", "rainy day"}, {"food", "event", "plan", "deal"})]
        return _format_items(items, f"For a short visit around **{context.address}**, I would plan around these picks:")

    useful = ranked[:4]
    return _format_items(useful, f"Here are the most useful source-backed picks around **{context.address}** right now:")


def answer_with_databricks(question: str, context: UserContext, ranked: list[RankedPick], fallback: str) -> str:
    """Answer through Databricks Model Serving when configured; otherwise use local intent fallback."""

    q = question.lower().strip()
    for char in "?!.":
        q = q.replace(char, "")
    q = q.strip()

    greetings = {
        "hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening",
        "greetings", "whats up", "what's up", "howdy", "hi there", "hello there", "how are you"
    }
    if q in greetings:
        return (
            f"Hello! I'm **Ask GoAround**, your hyperlocal discovery assistant. 😊\n\n"
            f"Since you're near **{context.address}**, I can help you find things like:\n"
            f"- 🍲 **Local Food & Coffee**: Hidden gems or cheap eats nearby.\n"
            f"- 🏷️ **Lobang & Deals**: Supermarket discounts and retail promotions.\n"
            f"- 🎪 **Things To Do**: Parks, events, and family activities.\n"
            f"- ☔ **Weather-Aware Ideas**: Great indoor plans if it's rainy outside.\n\n"
            f"What are you in the mood for today?"
        )

    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    endpoint = os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    if not (host and token):
        return fallback_answer(question, context, ranked, fallback)

    if not (host.startswith("http://") or host.startswith("https://")):
        host = f"https://{host}"

    prompt = (
        "You are Ask GoAround, a Singapore hyperlocal discovery assistant. "
        "Use only the supplied source-backed cards and context. "
        "Do not invent promotions, events, incidents, prices, timings or official claims. "
        "If a claim needs verification, say to check the source URL. "
        "Give a practical short answer with 3-5 bullets.\n\n"
        f"Question: {question}\n"
        f"Facts: {build_agent_facts(context, ranked)}"
    )
    try:
        r = requests.post(
            f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 550},
            timeout=45,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"Databricks Model Serving fallback used: {exc}\n\n{fallback_answer(question, context, ranked, fallback)}"
