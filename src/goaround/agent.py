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


def answer_with_databricks(question: str, context: UserContext, ranked: list[RankedPick], fallback: str) -> str:
    """Answer through Databricks Model Serving when configured."""

    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    endpoint = os.getenv("DATABRICKS_MODEL_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    if not (host and token):
        return fallback

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
        return f"Databricks Model Serving fallback used: {exc}\n\n{fallback}"
