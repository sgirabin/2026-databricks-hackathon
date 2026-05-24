from __future__ import annotations

import os
from databricks import sql


def main():
    print("Initializing Databricks Delta Tables for GoAround SG...")

    # Load parameters with identical defaults/rules as app_template_layout_test.py
    raw_host = os.getenv("DATABRICKS_SERVER_HOSTNAME") or os.getenv("DATABRICKS_HOST") or "dbc-68521f65-774f.cloud.databricks.com"
    host = raw_host.replace("https://", "").replace("http://", "").strip("/")
    http_path = os.getenv("DATABRICKS_HTTP_PATH") or "/sql/1.0/warehouses/e3ab5c87926da4b9"
    token = os.getenv("DATABRICKS_TOKEN")

    catalog = os.getenv("GOAROUND_CATALOG", "workspace")
    if catalog == "goaround_sg":
        catalog = "workspace"
    schema = os.getenv("GOAROUND_SCHEMA", "goaround_sg")

    table = f"{catalog}.{schema}.business_promotions"

    print(f"Server Hostname: {host}")
    print(f"HTTP Path: {http_path}")
    print(f"Target Delta Table: {table}")

    create_query = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id STRING,
            card_type STRING,
            category STRING,
            title STRING,
            description STRING,
            source_name STRING,
            source_url STRING,
            lat DOUBLE,
            lon DOUBLE,
            location_name STRING,
            valid_until STRING,
            tags STRING,
            source_reliability DOUBLE,
            freshness_score DOUBLE,
            submitted_at STRING
        ) USING delta
    """

    try:
        with sql.connect(server_hostname=host, http_path=http_path, access_token=token) as conn:
            print("Connected to Databricks SQL Warehouse successfully.")
            with conn.cursor() as cursor:
                print(f"Executing table creation for {table}...")
                cursor.execute(create_query)
                print("Table created or verified successfully in Delta Lake.")
    except Exception as exc:
        print(f"Error initializing Databricks SQL Table: {exc}")
        print("Fallback local storage will be utilized during application runtime.")


if __name__ == "__main__":
    main()
