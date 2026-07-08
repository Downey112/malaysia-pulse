# Malaysia Pulse

State-level cost-of-living indicators (CPI, fuel prices, labour force) for Malaysia,
sourced live from the official [data.gov.my](https://data.gov.my) Open API.

Built as a full data application — not just a dashboard — to show the full pipeline:
data ingestion → database → API → frontend, deployed across free-tier cloud services.

## Architecture

```
data.gov.my API  →  Python ETL (scheduled via GitHub Actions)
                        ↓
                  PostgreSQL (Supabase)
                        ↓
                  FastAPI backend (Render)
                        ↓
                  React dashboard (Vercel)
```

No paid infrastructure required — every piece below runs on a genuinely free tier,
no credit card needed anywhere.

## Repo structure

```
etl/                  Local ETL script + schema (run manually first, then scheduled via GitHub Actions)
backend/               FastAPI app serving the data
frontend/              React (Vite) dashboard
azure-function/        Optional — alternate scheduled-ETL path if you have Azure
                        credit available. Not used in the default deployment below;
                        the GitHub Actions workflow replaces it.
```

---

## Before you start

You'll need:
- Python 3.11+, Node 18+, Git
- Free accounts (all sign-up-with-GitHub, no card required): [Supabase](https://supabase.com), [Render](https://render.com), [Vercel](https://vercel.com)
- A local PostgreSQL install for development (or skip straight to Supabase and develop against that instead)

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

**Note on the API's pagination**: `api.data.gov.my` only documents `id` and `limit`
as query parameters — there's no `offset`/page parameter. `fetch_data.py` fetches
each dataset in a single request with a large `limit` rather than looping with an
offset (an earlier version of this script assumed offset pagination was supported;
it wasn't, and looked like an infinite hang as a result — don't reintroduce that
pattern without testing it directly against the API first).

## Part 2 — Local database + first ETL run (Day 2–4)

If you have Postgres locally:

```bash
createdb malaysia_pulse
psql malaysia_pulse -f etl/schema.sql

cp .env.example .env   # fill in DATABASE_URL
export $(cat .env | xargs)
python etl/fetch_data.py --dataset cpi_state
python etl/fetch_data.py --dataset cpi_state_inflation
python etl/fetch_data.py --dataset fuelprice
python etl/fetch_data.py --dataset lfs_qtr_state
```

(Running one dataset per command isn't strictly necessary locally — it matters more
when an agent/automation wrapper is watching for output — but it's a fine habit
either way since it makes a stuck dataset obvious immediately.)

Check it worked:

```bash
psql malaysia_pulse -c "SELECT dataset_id, count(*) FROM fact_indicator GROUP BY dataset_id;"
```

Expect roughly: `cpi_state` and `cpi_state_inflation` in the tens of thousands of
rows, `fuelprice` and `lfs_qtr_state` in the low thousands. If a dataset returns 0
facts, or a raw-row count near 200,000 (the script's single-request ceiling), go
back to `explore_api.py`'s output — something about that dataset's shape differs
from what `fetch_data.py` assumes.

## Part 3 — Backend locally (Day 4–6)

```bash
cd backend
pip install -r requirements.txt
export DATABASE_URL="postgresql://..."   # same one as above
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` — FastAPI's auto-generated Swagger UI. Try
`/latest`, `/compare?dataset_id=cpi_state&metric=index_overall`, and `/indicators`.
This is also a good screenshot for your README later — Swagger docs read well
to a recruiter skimming your repo.

**Note**: `cpi_state`'s `division` field gets folded into the metric name (see the
schema design note in `etl/schema.sql`), so the real metric names are things like
`index_overall`, `index_01`, `index_02`, etc. — not plain `index`. Run
`SELECT DISTINCT metric FROM fact_indicator WHERE dataset_id = 'cpi_state';`
to see the exact list before wiring up the frontend.

## Part 4 — Frontend locally (Day 6–9)

```bash
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env
npm run dev
```

Update `DEFAULT_DATASET` / `DEFAULT_METRIC` in `App.jsx` to match the real metric
names from Part 3. Also worth knowing: `cpi_state` is state-level only — there's no
national "malaysia" row — so the trend chart needs a real state as its default (and
ideally a dropdown to switch between states, not just a hardcoded one). This is the
part worth spending real design time on for the portfolio — a working chart is the
baseline, a good filtering/comparison UX is what makes it memorable.

At this point you have a fully working local app. Commit it before deploying anywhere —
deployment issues are much easier to debug against a version you know works.

```bash
git init
git add .
git commit -m "Working local version: ETL, API, frontend"
```

Push it to GitHub now too, even before deploying — Render and Vercel both deploy by
connecting directly to a GitHub repo, so you'll want it there first:

```bash
# create a new repo on github.com first, then:
git remote add origin https://github.com/<your-username>/malaysia-pulse.git
git push -u origin main
```

---

## Part 5 — Deploy (Day 9–14)

### Supabase (database)

1. [supabase.com](https://supabase.com) → sign in with GitHub → **New Project**
2. Pick a name, generate/save a database password, pick a region close to Malaysia
   (Singapore is usually the closest available)
3. Once the project's ready, go to **Project Settings → Database** and copy the
   **connection string** — use the **connection pooling** (port 6543) string rather
   than the direct one, it's the more standard choice for an app server talking to
   Supabase
4. Run the schema against it:
   ```bash
   psql "<your-supabase-connection-string>" -f etl/schema.sql
   ```
5. Run the ETL against it once manually, same as Part 2, using this connection
   string as `DATABASE_URL`

**Worth knowing**: Supabase free projects pause after 7 days with zero database
activity. The scheduled GitHub Actions ETL run below (which runs daily) doubles as
a keep-alive automatically, since it's a real write to the database — you shouldn't
need any extra workaround for that as long as the schedule keeps running.

### Render (backend)

1. [render.com](https://render.com) → sign in with GitHub → **New → Web Service**
2. Connect the `malaysia-pulse` repo, set **Root Directory** to `backend`
3. **Runtime**: Python 3
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:$PORT`
   (same command as `backend/startup.txt`, but note Render assigns its own `$PORT`
   — don't hardcode 8000 here like the Azure version did)
6. Add an environment variable: `DATABASE_URL` = your Supabase pooled connection string
7. Choose the **Free** instance type, deploy

**Worth knowing**: free Render web services spin down after 15 minutes with no
traffic, and take 30–60 seconds to wake up on the next request. Fine for a
portfolio piece, but worth a one-line note in your README so a recruiter clicking
the live link isn't confused by a slow first load — or set up a free
[UptimeRobot](https://uptimerobot.com) ping every 10 minutes if you'd rather avoid
cold starts entirely for a live demo.

### Vercel (frontend)

1. [vercel.com](https://vercel.com) → sign in with GitHub → **Add New → Project**
2. Import the `malaysia-pulse` repo, set **Root Directory** to `frontend`
3. Framework preset should auto-detect as Vite
4. Add an environment variable: `VITE_API_BASE_URL` = your Render backend's URL
   (something like `https://malaysia-pulse-api.onrender.com`)
5. Deploy

Vercel redeploys automatically on every push to `main` from here on, same as Render.

### GitHub Actions (scheduled ETL)

Replace the Azure Function timer trigger with a scheduled GitHub Actions workflow —
same idea, no separate cloud service needed since it runs on GitHub's own infrastructure
for free on a public repo.

1. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**
   — name it `DATABASE_URL`, value is your Supabase pooled connection string
2. Add `.github/workflows/scheduled-etl.yml` (see the file already included in this repo)
3. Commit and push — you can also trigger it manually via the **Actions** tab
   (**Run workflow** button) to confirm it works before waiting for the schedule

## Part 6 — Polish for GitHub (Day 14–17)

- Add the live Vercel URL and a screenshot to the top of this README
- Write a 3–4 bullet "insights" section — actual findings from the data, e.g. which
  state's CPI has risen fastest, how fuel prices track against CPI transport index
- Clean commit history if needed (`git rebase -i` to squash "wip" commits)
- Add a short "Why this architecture" section explaining the long-format schema
  decision and why these particular free-tier services were chosen — this is what
  turns a repo into a talking point in an interview, not just a checkbox

---

## Cost note

Every service here — Supabase, Render, Vercel, GitHub Actions — is free at this
project's scale, no credit card required anywhere. The trade-offs are operational,
not financial: Render's backend sleeps after 15 minutes idle (30–60s cold start on
wake), and Supabase pauses after 7 days with zero activity (the daily scheduled ETL
prevents this automatically). Neither matters for a portfolio piece that's mostly
viewed on demand rather than under constant traffic.

## Troubleshooting

- **ETL inserts 0 rows for a dataset**: field names differ from `DATASET_CONFIG` —
  rerun `explore_api.py` and check the printed sample.
- **A single dataset's raw row count lands suspiciously close to 200,000**: that's
  `fetch_data.py`'s single-request ceiling — the dataset may be larger than expected
  and truncated. Increase `SINGLE_REQUEST_LIMIT` and re-run, don't just trust the
  partial result.
- **Backend can't connect to Supabase**: double-check you're using the *pooled*
  connection string (port 6543), not the direct one (port 5432) — and that
  `sslmode=require` is present if Supabase's connection string doesn't already
  include it.
- **Frontend shows "Couldn't reach the API"**: `VITE_API_BASE_URL` is a build-time
  variable — it must be set in Vercel's project environment variables (and the
  project redeployed after adding it), not just in a local `.env` file which never
  reaches the Vercel build.
- **First load after a while is slow**: expected — that's Render's free-tier cold
  start, not a bug. A second request right after will be fast.
- **Supabase dashboard shows "Project paused"**: click **Restore project**, wait
  ~30 seconds, then retry. If this happens often, check whether the scheduled
  GitHub Actions ETL run is actually succeeding (check the Actions tab) — a failing
  or disabled schedule stops acting as a keep-alive too.
