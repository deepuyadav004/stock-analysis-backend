# Stock Backend

Backend service for sector-level stock signal generation using:
- Starlette API for health checks
- PostgreSQL (Supabase-compatible) storage
- NSE and market data ingestion scripts
- Multi-source financial news scraping
- FinBERT-based sentiment analysis
- Rule-based prediction pipeline

## What This Project Does

This project builds daily sector signals by combining:
1. Current-day sector sentiment from scraped financial news
2. Previous-day sentiment and prediction history
3. Rule-based scoring to generate `UP`, `DOWN`, or `NEUTRAL`

The output is stored in `sector_predictions`.

## Repository Structure

- `app/main.py`: API entrypoint (`/health`, `/health/db`)
- `app/core/config.py`: environment config loader
- `app/core/database.py`: SQLAlchemy engine/session setup
- `app/schemas/schema.sql`: core DB schema
- `app/schemas/apply_constraints.py`: one-off unique constraints migration
- `app/scrapers/import_companies_once.py`: company/listing ingest
- `app/scrapers/import_nse_company_metadata_once.py`: sector/industry/shares enrichment
- `app/scrapers/import_nse_price_history.py`: historical OHLCV import
- `app/scrapers/News_Scrappers/news_scraper.py`: scrape + tag + sentiment save
- `app/models/SentimentAnalyzer/analyzer.py`: FinBERT wrapper
- `app/models/FeatureBuilder/builder.py`: feature preparation
- `app/models/PredictionModel/model.py`: prediction + persistence
- `run_daily_pipeline.py`: full daily pipeline run

## Prerequisites

1. Python 3.11 (recommended)
2. PostgreSQL database
3. Network access to external data sources:
   - nseindia.com
   - economictimes.indiatimes.com
   - moneycontrol.com
   - livemint.com
   - 5paisa.com

> Note: Your workspace currently uses Python 3.14. Some ML packages (especially `transformers` stack) can lag behind newest Python versions. If installation/runtime fails, use Python 3.11 for this project.

## Setup

### 1. Create and activate virtual environment

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

First install what is already in `requirements.txt`:

```powershell
pip install -r requirements.txt
```

Then install additional packages used in code (if not already present):

```powershell
pip install httpx beautifulsoup4 transformers torch
```

### 3. Configure environment

Create `.env` in project root:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

The app normalizes this to `postgresql+psycopg2://...` and appends `sslmode=require` automatically when missing.

## Database Initialization

1. Create database.
2. Apply schema from `app/schemas/schema.sql`.
3. Run one-off constraints script:

```powershell
python app/schemas/apply_constraints.py
```

If you are using Supabase, prefer the pooler connection URL for better local connectivity.

## Run the API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health checks:
- `GET /health`
- `GET /health/db`

## Data and Pipeline Commands

### Import companies and listings

```powershell
python app/scrapers/import_companies_once.py
```

### Import NSE company metadata (sector/industry/shares)

```powershell
python app/scrapers/import_nse_company_metadata_once.py
```

Optional flags:
- `--symbol TCS`
- `--limit 20`
- `--dry-run`

### Import historical NSE prices

```powershell
python app/scrapers/import_nse_price_history.py --years 10
```

Optional flags:
- `--symbol TCS`
- `--limit 10`
- `--sleep-seconds 0.2`

### Run only news scraping + sentiment (with DB save)

```powershell
python app/scrapers/News_Scrappers/news_scraper.py --save
```

### Run full daily pipeline

```powershell
python run_daily_pipeline.py
```

### Automatic weekly NSE price sync on Vercel (Sunday 03:00 IST)

This repo now includes `vercel.json` cron config:

- Path: `/v1/jobs/weekly-nse-price-history`
- Schedule: `30 21 * * 6` (UTC), which is `03:00` IST Sunday

How it works:

1. Vercel Cron calls `GET /v1/jobs/weekly-nse-price-history` at `21:30 UTC` Saturday.
2. Endpoint runs weekly NSE price importer for the most recent 7 days.
3. Importer upserts OHLCV candles into `stock_prices` with conflict-safe updates.
4. This weekly cron endpoint currently runs without `CRON_SECRET` for now.

### Automatic daily pipeline trigger via GitHub Actions

This repo includes `.github/workflows/daily-pipeline-trigger.yml`:

- Schedule: `30 21 * * *` (UTC), which is `03:00` IST daily
- Action: calls your deployed API endpoint `/v1/jobs/daily-pipeline`

Required GitHub repository secrets:

- `PIPELINE_TRIGGER_URL`: full URL, for example `https://<your-vercel-domain>/v1/jobs/daily-pipeline`
- `CRON_SECRET` (optional but recommended): same value configured in your backend environment

Required backend environment variable:

- `CRON_SECRET` (optional): used by the endpoint to authorize scheduler calls.
   - If set: endpoint requires `Authorization: Bearer <CRON_SECRET>`.
   - If not set: endpoint allows unauthenticated calls.

Optional manual trigger endpoint:

- `GET /v1/jobs/daily-pipeline`
- Requires `Authorization: Bearer <CRON_SECRET>`
- Useful if you prefer HTTP-triggered jobs from an external scheduler.

## Can You Start This Project Now?

Yes, you can start it locally after these conditions are met:
1. Use a compatible Python version (prefer 3.11)
2. Install all dependencies (including missing scraper/ML packages)
3. Set `DATABASE_URL`
4. Ensure database schema exists

Without `DATABASE_URL`, app startup/import will fail by design.

## Deployment on Netlify

Short answer: **not recommended for this backend**.

Why:
- Netlify is optimized for static sites and serverless functions.
- This backend is designed as a long-running Python service.
- Scraping + FinBERT inference + DB-heavy jobs are not a good fit for Netlify function limits.
- Daily pipeline/scheduled ingestion is better on worker/cron-friendly platforms.

Recommended deployment split:
1. Deploy frontend (if any) on Netlify
2. Deploy this Python backend on Vercel, Railway, Fly.io, or a VPS
3. Use platform cron/scheduler for `run_daily_pipeline.py`

If you still want Netlify-only:
- You would need to re-architect into short-lived serverless handlers
- Move pipeline jobs out of request path
- Handle model cold starts and package size constraints

## Suggested Production Flow

1. API service hosts health + read endpoints
2. Scheduled job runs:
   - news scrape/sentiment
   - feature build
   - prediction save
3. Clients query predictions from database/API

## Troubleshooting

- `DATABASE_URL is not set`: add `.env` at root.
- DB connectivity issues on Supabase: use pooler URL and SSL.
- Import errors for `bs4`, `httpx`, or `transformers`: install missing packages.
- Scrapers blocked/HTTP errors: retry later; sources may rate-limit or change HTML structure.

## Notes

- `__pycache__` folders are generated caches and should stay ignored in Git.
- This repo currently includes utility/probe/test scripts for manual validation (`test_nse_api.py`, `test_sentiment.py`, etc.).
