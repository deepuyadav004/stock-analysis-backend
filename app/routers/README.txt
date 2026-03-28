Module: API Routers (Chunk 6 Update)

1. Purpose
Expose HTTP endpoints for backend clients with advanced filtering and sorting.

2. Problem Solved
Provides stable entry points for mobile app data retrieval with support for sector filtering, sorting, and pagination.

3. File Responsibilities
- home.py: Chunk 1-3 endpoints with filtering (signals, trends, detail, etc).
- insights.py: Chunk 4 endpoints for compare and stability insights.
- jobs.py: Protected endpoint(s) for cron-triggered backend jobs.
- test.py: Lightweight service availability endpoint.
- __init__.py: Package marker.

4. Step-by-Step Flow
1. `GET /v1/sectors/signals` receives filters (`signal`, `confidence_min`, `confidence_max`, `limit`, `offset`, `sort`).
2. `GET /v1/insights/sector-compare` computes 7/30-day market summary and strongest/weakest sectors.
3. `GET /v1/insights/signal-stability` computes per-sector signal flips and stability ratio.
4. `GET /v1/meta/version` returns lightweight API release metadata.
5. `GET /v1/meta/diagnostics` returns dataset health counts for app diagnostics.
6. `GET /v1/jobs/daily-pipeline` runs the daily pipeline when called by cron with valid bearer auth.

5. Interactions
- Uses app/core/database.py for DB engine.
- Mounted by app/main.py.
- Serves data to Android remote layer (Chunk 1-6 endpoints).

6. Assumptions
- Schema tables sector_predictions and sector_sentiment_daily are populated.
- Snapshot date is daily, not real-time.
- Signal enum: UP, DOWN, NEUTRAL
- Confidence values are [0, 1]
- CRON_SECRET is configured in deployment environment for job endpoint authorization.

7. Future Improvements
- Move SQL into service layer.
- Add response schema validation.
- Add caching for repeated snapshot requests with same filters.
- Add indices on (sector_id, date) and (signal, confidence) for faster filtering.
- Add historical rollup tables for faster multi-window insights queries.
