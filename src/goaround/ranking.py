from __future__ import annotations

import math
from datetime import datetime

from .models import PickCard, RankedPick, UserContext


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_score(distance_m: float | None, radius_m: int) -> float:
    if distance_m is None:
        return 0.45
    if distance_m <= 250:
        return 1.0
    if distance_m <= radius_m:
        return max(0.2, 1 - (distance_m / max(radius_m, 1)) * 0.75)
    return 0.0


def time_context_score(card: PickCard, context: UserContext) -> float:
    tags = {t.lower() for t in card.tags}
    tod = context.time_of_day.lower()
    if tod == "morning" and tags.intersection({"breakfast", "coffee", "commute", "weather"}):
        return 1.0
    if tod == "lunch" and tags.intersection({"lunch", "food", "deal", "cheap food"}):
        return 1.0
    if tod == "evening" and tags.intersection({"dinner", "grocery", "event", "family"}):
        return 1.0
    if tod == "weekend" and tags.intersection({"weekend", "family", "event", "tourist", "fitness"}):
        return 1.0
    return 0.55


def interest_score(card: PickCard, context: UserContext) -> float:
    interests = {x.lower() for x in context.interests}
    tags = {x.lower() for x in card.tags}
    category = card.category.lower()
    card_type = card.card_type.lower()
    if category in interests or card_type in interests:
        return 1.0
    if tags.intersection(interests):
        return 1.0
    mode = context.mode.lower()
    if mode == "visitor" and tags.intersection({"tourist", "local food", "rainy day", "short plan"}):
        return 1.0
    if mode == "resident" and tags.intersection({"grocery", "community", "local update", "transport"}):
        return 0.85
    if mode == "worker/student" and tags.intersection({"lunch", "coffee", "after work", "transport"}):
        return 0.9
    return 0.45


def weather_boost(card: PickCard, context: UserContext) -> float:
    weather = (context.weather or "").lower()
    tags = {x.lower() for x in card.tags}
    if any(x in weather for x in ["rain", "showers", "thundery"]):
        if tags.intersection({"indoor", "rainy day", "mall", "transport", "weather"}):
            return 0.15
        if tags.intersection({"outdoor", "jogging"}):
            return -0.20
    return 0.0


def source_score(card: PickCard) -> float:
    if not card.has_source():
        return 0.0
    return max(0.0, min(1.0, card.source_reliability))


def compute_why(card: PickCard, context: UserContext, distance_m: float | None) -> str:
    reasons: list[str] = []
    if distance_m is not None:
        reasons.append(f"within {distance_m:.0f}m of your selected area")
    overlap = sorted(set(x.lower() for x in card.tags).intersection(set(x.lower() for x in context.interests)))
    if overlap:
        reasons.append("matches your interest: " + ", ".join(overlap[:2]))
    if context.mode.lower() == "visitor" and "tourist" in {x.lower() for x in card.tags}:
        reasons.append("useful for visitors")
    if card.business_submitted:
        reasons.append("business-submitted promotion with source link")
    if not reasons:
        reasons.append("ranked as a useful local pick from source-backed data")
    return "Shown because it is " + "; ".join(reasons) + "."


def rank_cards(cards: list[PickCard], context: UserContext, limit: int = 12) -> list[RankedPick]:
    ranked: list[RankedPick] = []
    for card in cards:
        if not card.has_source():
            continue
        distance_m = None
        if card.lat is not None and card.lon is not None:
            distance_m = haversine_m(context.lat, context.lon, card.lat, card.lon)
            if distance_m > context.radius_m * 1.5:
                continue
        score = (
            0.28 * distance_score(distance_m, context.radius_m)
            + 0.24 * interest_score(card, context)
            + 0.18 * time_context_score(card, context)
            + 0.14 * source_score(card)
            + 0.12 * max(0.0, min(1.0, card.freshness_score))
            + weather_boost(card, context)
        )
        if card.business_submitted:
            score += 0.04
        ranked.append(RankedPick(card=card, score=round(score, 4), distance_m=distance_m, why_shown=compute_why(card, context, distance_m)))
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:limit]


def infer_time_of_day(now: datetime | None = None) -> str:
    now = now or datetime.now()
    if now.weekday() >= 5:
        return "weekend"
    if now.hour < 11:
        return "morning"
    if now.hour < 15:
        return "lunch"
    return "evening"
