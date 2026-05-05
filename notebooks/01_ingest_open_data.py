# Databricks notebook source
# MAGIC %md
# MAGIC # HomeWise SG - 01 Ingest Open Data
# MAGIC Ingests Singapore open datasets into Unity Catalog Delta tables.

# COMMAND ----------

import os, re, json, requests, pandas as pd
from pyspark.sql import functions as F

dbutils.widgets.text('catalog', os.getenv('HOMEWISE_CATALOG', 'main'))
dbutils.widgets.text('schema', os.getenv('HOMEWISE_SCHEMA', 'homewise_sg'))
CATALOG = dbutils.widgets.get('catalog')
SCHEMA = dbutils.widgets.get('schema')
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}')
spark.sql(f'USE CATALOG {CATALOG}')
spark.sql(f'USE SCHEMA {SCHEMA}')

DATASTORE_URL = 'https://data.gov.sg/api/action/datastore_search'
HEADERS = {'User-Agent': 'homewise-sg-hackathon/0.1'}
if os.getenv('DATA_GOV_API_KEY'):
    HEADERS['x-api-key'] = os.getenv('DATA_GOV_API_KEY')

DATASETS = {
    'hdb_resale': 'd_8b84c4ee58e3cfc0ece0d773c8ca6abc',
    'schools': 'd_688b934f82c1059ed0a6993d2a829089',
    'preschools': 'd_696c994c50745b079b3684f0e90ffc53',
}

# COMMAND ----------

def clean_cols(pdf):
    pdf = pdf.copy()
    pdf.columns = [re.sub(r'[^a-z0-9]+', '_', c.strip().lower()).strip('_') for c in pdf.columns]
    return pdf.drop(columns=['_id'], errors='ignore')


def datastore_search(dataset_id, limit=5000):
    rows, offset = [], 0
    while True:
        r = requests.get(DATASTORE_URL, params={'resource_id': dataset_id, 'limit': limit, 'offset': offset}, headers=HEADERS, timeout=60)
        r.raise_for_status()
        result = r.json()['result']; page = result.get('records', [])
        rows.extend(page); offset += len(page)
        if not page or offset >= result.get('total', offset): break
    return clean_cols(pd.DataFrame(rows))

# COMMAND ----------

for name, dataset_id in DATASETS.items():
    pdf = datastore_search(dataset_id)
    spark.createDataFrame(pdf.astype(str)).write.mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{CATALOG}.{SCHEMA}.bronze_{name}')

hdb = spark.table(f'{CATALOG}.{SCHEMA}.bronze_hdb_resale')
for col in ['resale_price', 'floor_area_sqm']:
    if col in hdb.columns: hdb = hdb.withColumn(col, F.col(col).cast('double'))
if 'month' in hdb.columns:
    hdb = hdb.withColumn('month_date', F.to_date(F.concat(F.col('month'), F.lit('-01'))))
    hdb = hdb.withColumn('quarter', F.concat(F.year('month_date'), F.lit('Q'), F.quarter('month_date')))
for col in ['town','flat_type','street_name','block']:
    if col in hdb.columns: hdb = hdb.withColumn(col, F.upper(F.trim(F.col(col))))
hdb.write.mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{CATALOG}.{SCHEMA}.silver_hdb_resale')

spark.sql(f'''
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.vw_resale_quarterly AS
SELECT town, flat_type, quarter, percentile_approx(resale_price, 0.5) AS median_resale_price, count(*) AS transactions
FROM {CATALOG}.{SCHEMA}.silver_hdb_resale
WHERE resale_price IS NOT NULL
GROUP BY town, flat_type, quarter
''')
print('HomeWise SG ingestion completed')
