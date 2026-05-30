# Chat recommendation map UI

Branch: `feature/chat-recommendation-map`
Base: `feature/polished-template-ui`

## UX rule

When Ask GoAround answers a recommendation-style question, the chat should stay text-first and render only a compact map block:

- maximum 3 recommendations
- one mini map with numbered pins
- compact cards below the map
- details hidden inside expanders
- actions limited to Directions and Source
- larger map opened separately instead of crowding the chat window

## Added component

`src/goaround/recommendation_map_ui.py` provides:

- `should_show_recommendation_map(prompt, ranked_items)`
- `recommendation_payload(ranked_items, limit=3)`
- `render_recommendation_map_block(ranked_items, context, limit=3, key_prefix="chat-recs")`

The component works with the existing `RankedPick` and `UserContext` models.

## Intended chat integration

In the Ask GoAround submit handler, after the assistant answer is rendered, call:

```python
from src.goaround.recommendation_map_ui import (
    render_recommendation_map_block,
    should_show_recommendation_map,
)

if should_show_recommendation_map(user_query, ranked_physical_picks):
    render_recommendation_map_block(
        ranked_physical_picks,
        context,
        limit=3,
        key_prefix=f"chat-map-{len(st.session_state['ask_messages'])}",
    )
```

For the current polished template, the best insertion point is in `app_template_layout_test.py`, inside the `if user_query:` block immediately after the assistant answer is appended/rendered.

## Why this avoids crowding

The chat bubble remains the explanation. The map block shows spatial context. Each card exposes only name, category, distance, score, and two actions by default. The reason and source metadata are hidden in an expander.
