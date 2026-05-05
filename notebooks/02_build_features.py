# Databricks notebook source
# MAGIC %md
# MAGIC # HomeWise SG - 02 Build Gold Features
# MAGIC Builds Genie-ready views for home buyer questions.

# COMMAND ----------

import os

dbutils.widgets.text('catalog', os.getenv('HOMEWISE_CATALOG', 'main'))
dbutils.widgets.text('schema', os.getenv('HOMEWISE_SCHEMA', 'homewise_sg'))
CATALOG = dbutils.widgets.get('catalog')
SCHEMA = dbutils.widgets.get('schema')
spark.sql(f'USE CATALOG {CATALOG}')
spark.sql(f'USE SCHEMA {SCHEMA}')

spark.sql(f'''
CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.gold_hdb_town_flat_summary AS
WITH latest_month AS (
  SELECT max(month_date) AS max_month FROM {CATALOG}.{SCHEMA}.silver_hdb_resale
), recent AS (
  SELECT * FROM {CATALOG}.{SCHEMA}.silver_hdb_resale, latest_month
  WHERE month_date >= add_months(max_month, -12)
), prior AS (
  SELECT * FROM {CATALOG}.{SCHEMA}.silver_hdb_resale, latest_month
  WHERE month_date < add_months(max_month, -12)
    AND month_date >= add_months(max_month, -24)
)
SELECT r.town,
       r.flat_type,
       percentile_approx(r.resale_price, 0.5) AS median_last_12m,
       count(*) AS txns_last_12m,
       percentile_approx(p.resale_price, 0.5) AS median_prior_12m,
       CASE WHEN percentile_approx(p.resale_price, 0.5) > 0
            THEN round((percentile_approx(r.resale_price, 0.5) - percentile_approx(p.resale_price, 0.5)) / percentile_approx(p.resale_price, 0.5) * 100, 2)
            ELSE NULL END AS yoy_pct
FROM recent r
LEFT JOIN prior p ON r.town = p.town AND r.flat_type = p.flat_type
GROUP BY r.town, r.flat_type
''')

spark.sql(f'''
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.genie_home_buyer_price_questions AS
SELECT * FROM {CATALOG}.{SCHEMA}.gold_hdb_town_flat_summary
''')

print('Gold features completed')
