-- HomeWise SG Genie / SQL examples
-- Replace main.homewise_sg if you use a different catalog/schema.

-- 1) Which HDB towns have the highest last-12-month median price for 4-room flats?
SELECT town, flat_type, median_last_12m, txns_last_12m, yoy_pct
FROM main.homewise_sg.gold_hdb_town_flat_summary
WHERE flat_type = '4 ROOM'
ORDER BY median_last_12m DESC
LIMIT 10;

-- 2) Which towns have high transaction liquidity but moderate YoY movement?
SELECT town, flat_type, median_last_12m, txns_last_12m, yoy_pct
FROM main.homewise_sg.gold_hdb_town_flat_summary
WHERE txns_last_12m >= 100
  AND yoy_pct BETWEEN -2 AND 5
ORDER BY txns_last_12m DESC;

-- Suggested Genie questions:
-- - What is the median resale trend for 4-room flats in Punggol?
-- - Which towns look affordable but still liquid?
-- - Which flat types had the highest YoY movement in the last 12 months?
