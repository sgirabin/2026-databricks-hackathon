from __future__ import annotations

from .models import PickCard


def source_registry_cards() -> list[PickCard]:
    """Source-backed seed cards.

    These cards intentionally link to official/source pages rather than inventing
    specific unsourced promotions or events. The ranking engine turns them into
    Today’s Picks and future Jobs/Agents can replace these with extracted cards.
    """

    return [
        PickCard(
            id="fairprice-promos",
            card_type="deal",
            category="grocery",
            title="Check FairPrice promotions near you",
            description="Useful grocery lobang source for weekly household shopping. Verify exact outlet, item and validity at source.",
            source_name="FairPrice Promotions",
            source_url="https://www.fairprice.com.sg/promotions",
            tags=("grocery", "deal", "resident", "budget", "weekly"),
            source_reliability=0.85,
            freshness_score=0.7,
        ),
        PickCard(
            id="shengsiong-promos",
            card_type="deal",
            category="grocery",
            title="Check Sheng Siong promotions",
            description="Grocery and household promotions source. Good for residents comparing weekly supermarket lobang.",
            source_name="Sheng Siong Promotions",
            source_url="https://shengsiong.com.sg/promotions",
            tags=("grocery", "deal", "resident", "budget", "weekly"),
            source_reliability=0.82,
            freshness_score=0.7,
        ),
        PickCard(
            id="coldstorage-promos",
            card_type="deal",
            category="grocery",
            title="Check Cold Storage promotions",
            description="Useful source for grocery and premium supermarket promotions. Verify availability at source.",
            source_name="Cold Storage Promotions",
            source_url="https://coldstorage.com.sg/promotions",
            tags=("grocery", "deal", "shopping"),
            source_reliability=0.82,
            freshness_score=0.65,
        ),
        PickCard(
            id="capitaland-promos",
            card_type="deal",
            category="mall",
            title="Mall promotions from CapitaLand",
            description="Dining, shopping and family activity promotions across CapitaLand malls. Useful when planning errands or weekends.",
            source_name="CapitaLand Mall Promotions",
            source_url="https://www.capitaland.com/sg/malls/promotions.html",
            tags=("mall", "deal", "shopping", "family", "weekend", "tourist"),
            source_reliability=0.8,
            freshness_score=0.65,
        ),
        PickCard(
            id="frasers-promos",
            card_type="deal",
            category="mall",
            title="Mall promotions from Frasers Property",
            description="Shopping and dining deals across Frasers malls. Good for weekend and after-work discovery.",
            source_name="Frasers Property Mall Promotions",
            source_url="https://www.frasersproperty.com/sg/malls/promotions",
            tags=("mall", "deal", "shopping", "family", "weekend"),
            source_reliability=0.8,
            freshness_score=0.65,
        ),
        PickCard(
            id="onepa-events",
            card_type="event",
            category="community",
            title="Find community events on OnePA",
            description="Search nearby community events and activities. Useful for residents and families planning the week or weekend.",
            source_name="OnePA Events",
            source_url="https://www.onepa.gov.sg/events",
            tags=("community", "event", "family", "weekend", "resident"),
            source_reliability=0.9,
            freshness_score=0.75,
        ),
        PickCard(
            id="nlb-events",
            card_type="event",
            category="family / learning",
            title="Library events and activities",
            description="NLB events can be useful for families, students and visitors looking for learning or indoor activities.",
            source_name="NLB Events",
            source_url="https://www.nlb.gov.sg/main/whats-on/events",
            tags=("event", "family", "learning", "indoor", "rainy day", "weekend"),
            source_reliability=0.9,
            freshness_score=0.75,
        ),
        PickCard(
            id="activesg-activities",
            card_type="event",
            category="fitness",
            title="ActiveSG activities and fitness ideas",
            description="Useful for fitness, sports and family activity planning. Verify programme timing at source.",
            source_name="ActiveSG Circle",
            source_url="https://www.activesgcircle.gov.sg/",
            tags=("fitness", "event", "sports", "weekend", "family"),
            source_reliability=0.82,
            freshness_score=0.65,
        ),
        PickCard(
            id="ura-masterplan",
            card_type="local_update",
            category="future plans",
            title="Check future development context",
            description="URA Draft Master Plan helps residents, visitors and potential movers understand future neighbourhood changes.",
            source_name="URA Draft Master Plan",
            source_url="https://www.uradraftmasterplan.gov.sg/",
            tags=("future plans", "local update", "resident", "buyer mode"),
            source_reliability=0.92,
            freshness_score=0.55,
        ),
        PickCard(
            id="lta-projects",
            card_type="local_update",
            category="transport",
            title="Check upcoming transport projects",
            description="Official LTA project updates for future connectivity and construction context.",
            source_name="LTA Upcoming Projects",
            source_url="https://www.lta.gov.sg/content/ltagov/en/upcoming_projects.html",
            tags=("transport", "local update", "future plans", "resident", "buyer mode"),
            source_reliability=0.9,
            freshness_score=0.55,
        ),
    ]


def area_anchor_cards(area_name: str, lat: float, lon: float) -> list[PickCard]:
    """Cards generated from user's selected area.

    These are source-backed search actions, not factual claims. They help the
    demo show local discovery while preserving source safety.
    """

    q = area_name.replace(" ", "+")
    return [
        PickCard(
            id="local-food-search",
            card_type="food",
            category="food",
            title=f"Find local food around {area_name}",
            description="Open a source-backed search for nearby food, hawker and food court options. Use this when deciding what to eat now.",
            source_name="Google Search",
            source_url=f"https://www.google.com/search?q={q}+nearby+food+hawker+food+court+Singapore",
            lat=lat,
            lon=lon,
            location_name=area_name,
            tags=("food", "local food", "lunch", "dinner", "tourist", "resident", "cheap food"),
            source_reliability=0.6,
            freshness_score=0.6,
        ),
        PickCard(
            id="local-events-search",
            card_type="event",
            category="things to do",
            title=f"What’s happening around {area_name}",
            description="Search for source-backed events, activities and things to do near the selected area.",
            source_name="Google Search",
            source_url=f"https://www.google.com/search?q={q}+events+activities+this+weekend+Singapore",
            lat=lat,
            lon=lon,
            location_name=area_name,
            tags=("event", "things to do", "weekend", "family", "tourist", "visitor"),
            source_reliability=0.6,
            freshness_score=0.65,
        ),
        PickCard(
            id="rainy-day-search",
            card_type="plan",
            category="rainy day",
            title=f"Rainy-day options near {area_name}",
            description="Indoor backup plan source search for rainy weather or family outings.",
            source_name="Google Search",
            source_url=f"https://www.google.com/search?q={q}+indoor+activities+rainy+day+Singapore",
            lat=lat,
            lon=lon,
            location_name=area_name,
            tags=("rainy day", "indoor", "family", "tourist", "weekend"),
            source_reliability=0.6,
            freshness_score=0.6,
        ),
    ]
