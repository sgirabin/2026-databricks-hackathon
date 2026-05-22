from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from .models import PickCard


def create_business_promo_card(
    *,
    business_name: str,
    title: str,
    description: str,
    category: str,
    source_url: str,
    lat: float,
    lon: float,
    location_name: str,
    valid_until: str | None,
    tags: list[str] | tuple[str, ...],
) -> PickCard:
    """Create a source-backed business promotion card.

    For the hackathon, cards are stored in Streamlit session state. In production,
    the same shape can be persisted in Lakebase and promoted into a Gold
    today_picks table after validation.
    """

    safe_tags = tuple(sorted({t.strip().lower() for t in tags if t and t.strip()}))
    return PickCard(
        id=f"business-{uuid4().hex[:10]}",
        card_type="deal",
        category=category or "business promo",
        title=title,
        description=description,
        source_name=business_name,
        source_url=source_url,
        lat=lat,
        lon=lon,
        location_name=location_name,
        end_at=valid_until,
        tags=safe_tags + ("business", "deal", "promotion"),
        source_reliability=0.68,
        freshness_score=0.9,
        business_submitted=True,
        metadata={"submitted_at": datetime.now().isoformat(timespec="seconds")},
    )
