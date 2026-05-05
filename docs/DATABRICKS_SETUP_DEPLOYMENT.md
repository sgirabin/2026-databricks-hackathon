# HomeWise SG - Databricks setup and deployment guide

This guide is written so you can follow it step by step for the Databricks hackathon demo.

The recommended path is:

1. Test the app locally.
2. Download / verify open data sources.
3. Push latest code to GitHub.
4. Create a Databricks App from Git.
5. Run Databricks notebooks to create Delta tables and SQL views.
6. Configure optional Model Serving / Genie / Lakebase.
7. Redeploy and demo.

---

## 0. What is already in this repository

Required app files:

```text
app.py
app.yaml
requirements.txt
.env.example
```

Databricks / data files:

```text
config/data_sources.yml
scripts/download_open_data.py
scripts/deploy_databricks_git.sh
scripts/deploy_databricks_workspace.sh
notebooks/01_ingest_open_data.py
notebooks/02_build_features.py
notebooks/03_genie_sql_examples.sql
```

`app.yaml` runs the app using Streamlit. Databricks Apps will install `requirements.txt` and then run the command from `app.yaml`.

---

## 1. Prerequisites

Install on your laptop:

- Python 3.10 or newer
- Git
- Databricks CLI
- Access to a Databricks workspace with Databricks Apps enabled
- Permission to create/deploy Databricks Apps
- Permission to create schema/tables in Unity Catalog if you run the notebooks

Install Databricks CLI if you do not have it yet:

```bash
pip install --upgrade databricks-cli
```

If your environment uses the newer standalone CLI installer, follow your workspace/company standard. Then check:

```bash
databricks --version
```

---

## 2. Clone and test locally first

```bash
git clone https://github.com/sgirabin/2026-databricks-hackathon.git
cd 2026-databricks-hackathon

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Windows PowerShell:

```powershell
git clone https://github.com/sgirabin/2026-databricks-hackathon.git
cd 2026-databricks-hackathon

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Test these addresses:

```text
308C Punggol Walk
1 Cantonment Road
1 Tanjong Pagar Plaza
```

Expected result:

- Address is matched by OneMap.
- HDB resale trend loads.
- Live amenities load.
- Map appears.
- Evidence tab shows credible-source search links.

---

## 3. Download and verify open data locally

This step is optional for running the app, because the app can load from APIs directly. It is useful for validating all sources and for Databricks ingestion.

```bash
python scripts/download_open_data.py --out data/raw
```

For a faster test:

```bash
python scripts/download_open_data.py --out data/raw --max-records 5000
```

Expected files:

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

All source links are listed in:

```text
config/data_sources.yml
```

---

## 4. Login to Databricks CLI

Replace the host with your workspace URL.

```bash
databricks auth login --host https://<your-workspace-url>
```

Verify identity:

```bash
databricks current-user me
```

If your company workspace requires profiles, create or select a profile and add `--profile <profile-name>` to CLI commands.

---

## 5. Deployment option A - Deploy Databricks App from GitHub UI

This is the easiest and cleanest option for a hackathon.

1. Open your Databricks workspace.
2. Go to **Compute**.
3. Open the **Apps** tab.
4. Click **Create app**.
5. App name: `homewise-sg`.
6. Choose Git repository deployment.
7. Repository URL:

```text
https://github.com/sgirabin/2026-databricks-hackathon
```

8. Git provider: `GitHub`.
9. Branch / Git reference: `main`.
10. Source code path: leave blank because the app is in the repository root.
11. Create the app.
12. Click **Deploy**.
13. After deployment completes, click the app URL.

Expected behavior:

- Databricks installs `requirements.txt`.
- Databricks reads `app.yaml`.
- Databricks runs:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $DATABRICKS_APP_PORT
```

---

## 6. Deployment option B - Deploy Databricks App from GitHub using CLI

First authenticate:

```bash
databricks auth login --host https://<your-workspace-url>
```

Then run:

```bash
export DATABRICKS_APP_NAME=homewise-sg
export GIT_REPO_URL=https://github.com/sgirabin/2026-databricks-hackathon
export GIT_BRANCH=main

./scripts/deploy_databricks_git.sh
```

If the CLI command fails because your Databricks CLI version has a different Apps syntax, use the UI method in section 5. The UI path is usually more reliable for first setup.

---

## 7. Deployment option C - Deploy from Databricks workspace folder

Use this if Git deployment is blocked by workspace policy.

```bash
export DATABRICKS_APP_NAME=homewise-sg
export DATABRICKS_WORKSPACE_PATH=/Workspace/Users/<your-email>/homewise-sg

./scripts/deploy_databricks_workspace.sh
```

Manual UI alternative:

1. Upload/sync the repository files to a Databricks workspace folder.
2. Go to **Compute > Apps**.
3. Create or open `homewise-sg`.
4. Click **Deploy**.
5. Choose the workspace folder containing `app.py`, `app.yaml`, and `requirements.txt`.
6. Deploy.

---

## 8. Configure environment variables / secrets

The app runs without most keys. For a stronger demo, configure these as Databricks App environment variables or secrets:

```text
DATA_GOV_API_KEY=
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
LAKEBASE_DATABASE_URL=
HOMEWISE_CATALOG=main
HOMEWISE_SCHEMA=homewise_sg
```

Minimum recommended for hackathon demo:

```text
HOMEWISE_CATALOG=main
HOMEWISE_SCHEMA=homewise_sg
```

Optional but useful:

```text
BING_SEARCH_KEY=
DATABRICKS_HOST=
DATABRICKS_TOKEN=
DATABRICKS_MODEL_ENDPOINT=
```

Security rule:

- Do not commit `.env`.
- Do not commit API keys.
- Use Databricks secrets or app environment configuration.

---

## 9. Run Databricks notebooks to create Lakehouse tables

In Databricks workspace:

1. Import or open the repository notebooks.
2. Run:

```text
notebooks/01_ingest_open_data.py
```

Widget values:

```text
catalog = main
schema = homewise_sg
```

This creates:

```text
main.homewise_sg.bronze_hdb_resale
main.homewise_sg.bronze_schools
main.homewise_sg.bronze_preschools
main.homewise_sg.silver_hdb_resale
main.homewise_sg.vw_resale_quarterly
```

Then run:

```text
notebooks/02_build_features.py
```

This creates:

```text
main.homewise_sg.gold_hdb_town_flat_summary
main.homewise_sg.genie_home_buyer_price_questions
```

Then open:

```text
notebooks/03_genie_sql_examples.sql
```

Use it to test SQL queries and create a Genie demo.

---

## 10. Optional - Create a Genie Space

1. In Databricks, go to Genie / Data Intelligence features.
2. Create a Genie Space.
3. Add these tables/views:

```text
main.homewise_sg.gold_hdb_town_flat_summary
main.homewise_sg.vw_resale_quarterly
main.homewise_sg.silver_hdb_resale
```

4. Suggested questions:

```text
What is the median resale trend for 4-room flats in Punggol?
Which towns have high transaction liquidity but moderate YoY movement?
Which flat types had the highest YoY movement in the last 12 months?
Which towns look more stable for a family buyer?
```

For hackathon demo, show Genie after the app, as the analytical back-office layer.

---

## 11. Optional - Configure Databricks Model Serving

If you have a model serving endpoint:

1. Get your workspace host:

```text
https://<your-workspace-url>
```

2. Set:

```text
DATABRICKS_HOST=https://<your-workspace-url>
DATABRICKS_TOKEN=<your-token-or-secret-reference>
DATABRICKS_MODEL_ENDPOINT=<your-serving-endpoint-name>
```

The app will call:

```text
/serving-endpoints/<endpoint>/invocations
```

If this is not configured, the app uses a deterministic fallback buyer summary.

---

## 12. Optional - Lakebase / Postgres memory

If you have Lakebase or another Postgres-compatible database, set:

```text
LAKEBASE_DATABASE_URL=postgresql://user:password@host:5432/database
```

Current app is Lakebase-ready, but persistent saved-search workflow can be expanded after the main demo works.

---

## 13. Redeploy after code changes

If deploying from Git:

```bash
git add .
git commit -m "Update HomeWise SG app"
git push origin main
```

Then in Databricks:

1. Open **Compute > Apps**.
2. Open `homewise-sg`.
3. Click **Deploy**.
4. Choose Git reference `main`.
5. Deploy.

---

## 14. Troubleshooting

### App does not start

Check:

- `app.yaml` is at repo root.
- `requirements.txt` is at repo root.
- `app.py` is at repo root.
- Logs tab in the Databricks App page.

### Streamlit port issue

`app.yaml` must use:

```yaml
--server.address
0.0.0.0
--server.port
$DATABRICKS_APP_PORT
```

### Dependencies fail

Run locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then fix `requirements.txt` before redeploying.

### OneMap geocoding fails

Try another input:

```text
308C Punggol Walk
1 Cantonment Road
1 Tanjong Pagar Plaza
```

If it still fails, the OneMap endpoint may be temporarily unavailable or blocked by the network.

### data.gov.sg loading fails

Run:

```bash
python scripts/download_open_data.py --out data/raw --max-records 5000
```

If this fails, check network/API availability and whether your workspace needs outbound internet access or proxy configuration.

### School/pre-school loading is slow

This is expected on first run because some records need geocoding. Reduce the sidebar settings:

```text
Max schools to geocode/cache = 100
Max pre-schools to geocode/cache = 200
```

### Git deployment fails for private repo

This repo is public now. If you make it private, configure Git credentials for the Databricks App service principal.

---

## 15. Recommended hackathon demo script

1. Open HomeWise SG app.
2. Search `308C Punggol Walk`.
3. Select `Family with young child`.
4. Show scorecard and buyer briefing.
5. Open `Live amenities map`.
6. Show nearest school, pre-school, hawker, supermarket and community club.
7. Open `Price trends`.
8. Filter to matching town / flat type.
9. Show comparable transactions and YoY movement.
10. Open `Evidence & future plans`.
11. Explain: no credible source = no sensitive claim.
12. Open `Databricks architecture`.
13. Explain: open data -> Delta tables -> Gold features -> Databricks App -> Model Serving / Genie.

---

## 16. Final checklist before submission

- [ ] App runs locally.
- [ ] App deploys in Databricks Apps.
- [ ] HDB resale data loads.
- [ ] Amenity map loads.
- [ ] Price trend chart works.
- [ ] Evidence tab does not make unsupported sensitive claims.
- [ ] Notebooks run and create Delta tables.
- [ ] Genie SQL examples run.
- [ ] README and data-source manifest are updated.
- [ ] Demo addresses prepared.
