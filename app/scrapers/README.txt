Module: Market Data Scrapers

1. Module Purpose
Provide source-data ingestion utilities that fetch market/company datasets and persist them into normalized DB tables.

2. Problem Solved
Centralizes external data fetch + transform + upsert logic so scheduled jobs can keep listings and price history current.

3. File Responsibilities
- import_companies_once.py: Imports company/listing universe from source API into exchanges, companies, listings.
- import_nse_company_metadata_once.py: Fetches NSE quote metadata and updates sectors, industries, and company attributes.
- import_nse_price_history.py: Fetches historical NSE OHLCV and upserts into stock_prices.
- nse_index_scraper.py: Fetches NSE advance/decline index data used by sentiment/feature logic.
- update_data_in_db.py: Wrapper CLI for running company/listing import.

4. Step-by-Step Flow
1. Load relevant symbols/listings from DB.
2. Bootstrap NSE session cookies by hitting an NSE page endpoint.
3. Call NSE API endpoint(s) for each symbol/window.
4. Normalize payload fields into DB schema columns.
5. Deduplicate row keys where needed.
6. Upsert in chunks using conflict-safe SQL.

5. Interactions with Other Modules
- app/core/database.py provides SQLAlchemy engine and transaction context.
- app/schedulers consumes scraper entrypoints for cron execution.
- app/routers/jobs.py can trigger scheduler wrappers over HTTP.

6. Assumptions
- NSE endpoints may require valid cookies/referer headers per session.
- Table constraints exist for conflict keys (for example stock_prices(listing_id, date)).
- DB credentials are available via environment configuration.

7. Future Improvements
- Add incremental watermark table to avoid scanning unchanged date ranges.
- Persist per-job metrics/failures to a job_runs table for observability.
- Add backoff jitter and API rate-limit guardrails.