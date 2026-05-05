# HomeWise SG data loading

This folder is intentionally kept mostly empty in Git. Use the scripts below to download open data locally or inside Databricks.

## 1. Review data source manifest

All required source links, dataset IDs and loader notes are in:

```text
config/data_sources.yml
```

The manifest includes:

- data.gov.sg dataset page links
- direct datastore API URLs
- direct poll-download URLs for GeoJSON datasets
- OneMap search API example
- official future-development sources
- credible news / agency domains

## 2. Download all configured data.gov.sg sources

```bash
python scripts/download_open_data.py --out data/raw
```

Optional quick sample run:

```bash
python scripts/download_open_data.py --out data/raw --max-records 5000
```

The script writes files like:

```text
data/raw/hdb_resale_2017_onwards.csv
data/raw/hdb_resale_price_index.csv
data/raw/hawker_centres_geojson.geojson
data/raw/schools_general_information.csv
data/raw/preschool_centres.csv
data/raw/community_clubs_geojson.geojson
data/raw/supermarkets_geojson.geojson
data/raw/download_summary.json
```

## 3. Load into Databricks

Use the notebooks:

```text
notebooks/01_ingest_open_data.py
notebooks/02_build_features.py
notebooks/03_genie_sql_examples.sql
```

The app itself can also load from APIs directly, so the local download step is optional for demo. For production-quality Databricks judging, run the notebooks to create Delta tables and views.

## 4. OneMap

OneMap is used for address/postal-code geocoding. The app currently uses the public OneMap search endpoint. If you later use authenticated OneMap APIs, set these in `.env`:

```dotenv
ONEMAP_EMAIL=
ONEMAP_PASSWORD=
ONEMAP_ACCESS_TOKEN=
```

## 5. Sensitive news / incident data

Sensitive property-history claims are not downloaded as a static dataset. The app only uses credible-source search links or Bing Search results when `BING_SEARCH_KEY` is configured. This avoids unsupported or defamatory claims.
