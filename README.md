# Malaysia Pulse

State-level cost-of-living indicators (CPI, fuel prices, labour force) for Malaysia,
sourced live from the official [data.gov.my](https://data.gov.my) Open API.

Built as a full data application — not just a dashboard — to show the full pipeline:
data ingestion → database → API → frontend, deployed on Azure.

## Architecture

```
data.gov.my API  →  Python ETL (Azure Function, timer trigger)
                        ↓
                  PostgreSQL Flexible Server (Azure)
                        ↓
                  FastAPI backend (Azure App Service)
                        ↓
                  React dashboard (Azure Static Web Apps)
```

## Repo structure

```
etl/                  Local ETL script + schema (run manually first)
azure-function/        Same ETL logic, packaged as a scheduled Azure Function
backend/               FastAPI app serving the data
frontend/               React (Vite) dashboard
```

---

## Before you start

You'll need:
- Python 3.11+, Node 18+, Git
- An Azure for Students account activated (azure.microsoft.com/free/students — no card needed, $100 credit, 12 months)
- Azure CLI installed (`az --version` to check) and Azure Functions Core Tools (`func --version`) for the Function App deploy step
- A local PostgreSQL install for development, OR just start directly with an Azure PostgreSQL server (see Part 3) and skip local Postgres entirely

---

## Part 1 — Explore the real data (Day 1)

Don't trust dataset documentation blindly. Run this first:

```bash
cd etl
pip install -r requirements.txt
python explore_api.py
```

This prints the actual field names for `cpi_state`, `cpi_state_inflation`, `fuelprice`,
and `lfs_qtr_state`. Compare them against the `DATASET_CONFIG` dict at the top of
`fetch_data.py` — the `date_field` / `state_field` assumptions there are best guesses
based on the API docs and may need small tweaks once you see real responses.

## Part 2 — Local database + first ETL run (Day 2–4)

If you have Postgres locally:

```bash
createdb malaysia_pulse
psql malaysia_pulse -f etl/schema.sql

cp .env.example .env   # fill in DATABASE_URL
export $(cat .env | xargs)
python etl/fetch_data.py
```

Check it worked:

```bash
psql malaysia_pulse -c "SELECT dataset_id, count(*) FROM fact_indicator GROUP BY dataset_id;"
```

You should see row counts for all four datasets. If a dataset returns 0 facts, go back
to the `explore_api.py` output — the field names in `DATASET_CONFIG` probably need
adjusting for that one dataset.

## Part 3 — Backend locally (Day 4–6)

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql://..."   # same one as above
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` — FastAPI's auto-generated Swagger UI. Try
`/latest`, `/compare?dataset_id=cpi_state&metric=index`, and `/indicators`.
This is also a good screenshot for your README later — Swagger docs read well
to a recruiter skimming your repo.

## Part 4 — Frontend locally (Day 6–9)

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev
```

`App.jsx` currently charts `cpi_state` / `index` by default — once you've confirmed
real metric names from Part 1, swap `DEFAULT_DATASET` / `DEFAULT_METRIC` and add a
picker so users can choose between CPI, fuel price, and labour force views. This is
the part worth spending real design time on for the portfolio — a working chart is
the baseline, a good filtering/comparison UX is what makes it memorable.

At this point you have a fully working local app. Commit it before moving to Azure —
deployment issues are much easier to debug against a version you know works.

```bash
git init
git add .
git commit -m "Working local version: ETL, API, frontend"
```

---

## Part 5 — Provision Azure resources (Day 9–11)

```bash
az login

az group create --name rg-malaysia-pulse --location southeastasia
```

**PostgreSQL Flexible Server** (Burstable B1ms is the cheapest tier that isn't the
free-for-12-months tier some regions offer — check the portal first, it may be free):

```bash
az postgres flexible-server create \
  --resource-group rg-malaysia-pulse \
  --name malaysia-pulse-db \
  --location southeastasia \
  --admin-user pulseadmin \
  --admin-password "<choose-a-strong-password>" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0-255.255.255.255

az postgres flexible-server db create \
  --resource-group rg-malaysia-pulse \
  --server-name malaysia-pulse-db \
  --database-name malaysia_pulse
```

`--public-access 0.0.0.0-255.255.255.255` opens it to all IPs, which is fine for a
demo project but worth narrowing (or switching to VNet integration) if you want to
mention security hygiene in an interview — a good talking point either way.

Your connection string:
```
postgresql://pulseadmin:<password>@malaysia-pulse-db.postgres.database.azure.com:5432/malaysia_pulse?sslmode=require
```

Run the schema against it:
```bash
psql "postgresql://pulseadmin:<password>@malaysia-pulse-db.postgres.database.azure.com:5432/malaysia_pulse?sslmode=require" -f etl/schema.sql
```

**App Service** (backend):

```bash
az appservice plan create \
  --name plan-malaysia-pulse \
  --resource-group rg-malaysia-pulse \
  --sku B1 \
  --is-linux

az webapp create \
  --resource-group rg-malaysia-pulse \
  --plan plan-malaysia-pulse \
  --name malaysia-pulse-api \
  --runtime "PYTHON:3.12"

az webapp config appsettings set \
  --resource-group rg-malaysia-pulse \
  --name malaysia-pulse-api \
  --settings DATABASE_URL="postgresql://pulseadmin:<password>@malaysia-pulse-db.postgres.database.azure.com:5432/malaysia_pulse?sslmode=require"

az webapp config set \
  --resource-group rg-malaysia-pulse \
  --name malaysia-pulse-api \
  --startup-file "gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000"
```

**Function App** (scheduled ETL):

```bash
az storage account create \
  --name malaysiapulsestorage \
  --resource-group rg-malaysia-pulse \
  --location southeastasia \
  --sku Standard_LRS

az functionapp create \
  --resource-group rg-malaysia-pulse \
  --consumption-plan-location southeastasia \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name malaysia-pulse-etl \
  --storage-account malaysiapulsestorage \
  --os-type Linux

az functionapp config appsettings set \
  --name malaysia-pulse-etl \
  --resource-group rg-malaysia-pulse \
  --settings DATABASE_URL="postgresql://pulseadmin:<password>@malaysia-pulse-db.postgres.database.azure.com:5432/malaysia_pulse?sslmode=require"
```

## Part 6 — Deploy (Day 11–14)

**Backend:**
```bash
cd backend
az webapp up --resource-group rg-malaysia-pulse --name malaysia-pulse-api --runtime "PYTHON:3.12"
```

**Function App:**
```bash
cd azure-function
func azure functionapp publish malaysia-pulse-etl
```

**Frontend** — easiest path is linking Static Web Apps directly to your GitHub repo,
which auto-generates a GitHub Actions workflow and redeploys on every push:

```bash
az staticwebapp create \
  --name malaysia-pulse-web \
  --resource-group rg-malaysia-pulse \
  --source https://github.com/<your-username>/malaysia-pulse \
  --location "eastasia" \
  --branch main \
  --app-location "frontend" \
  --output-location "dist" \
  --login-with-github
```

This opens a GitHub OAuth prompt and commits a `.github/workflows/azure-static-web-apps-*.yml`
file to your repo automatically. After that, add `VITE_API_BASE_URL` (pointing to
your App Service URL) as a repo secret or directly in the generated workflow's build
step, then push — it deploys itself.

## Part 7 — Polish for GitHub (Day 14–17)

- Add the live Static Web Apps URL and a screenshot to the top of this README
- Write a 3–4 bullet "insights" section — actual findings from the data, e.g. which
  state's CPI has risen fastest, how fuel prices track against CPI transport index
- Clean commit history if needed (`git rebase -i` to squash "wip" commits)
- Add a short "Why this architecture" section explaining the long-format schema
  decision and the Azure service choices — this is what turns a repo into a
  talking point in an interview, not just a checkbox

---

## Cost note

Azure for Students gives $100 credit, no card required, valid 12 months. Static Web
Apps and the Function App's consumption plan are free at this scale. The Postgres
Burstable B1ms server and App Service B1 plan are the only paid pieces — together
well under $100 even left running for the full build-and-demo period. Stop or delete
the resource group (`az group delete --name rg-malaysia-pulse`) once you're done
actively demoing it if you want to bank the remaining credit for something else.

## Troubleshooting

- **ETL inserts 0 rows for a dataset**: field names differ from `DATASET_CONFIG` —
  rerun `explore_api.py` and check the printed sample.
- **Backend can't connect to Postgres from App Service**: confirm the firewall rule
  from `--public-access` was applied, and that `sslmode=require` is in the connection
  string — Azure Postgres requires TLS by default.
- **Static Web App shows a blank page**: check the browser console for a failed
  `VITE_API_BASE_URL` fetch — it's a build-time variable, so it must be set in the
  GitHub Actions workflow, not just a local `.env` file.
