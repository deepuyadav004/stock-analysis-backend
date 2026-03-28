Module: API Routers (Chunk 3 Update)

1. Purpose
Expose HTTP endpoints for backend clients with advanced filtering and sorting.

2. Problem Solved
Provides stable entry points for mobile app data retrieval with support for sector filtering, sorting, and pagination.

3. File Responsibilities
- home.py: Chunk 1–3 endpoints with filtering (signals, trends, detail, etc).
- test.py: Lightweight service availability endpoint.
- __init__.py: Package marker.

4. Step-by-Step Flow
1. GET /v1/sectors/signals endpoint receives query params: signal, confidence_min, confidence_max, limit, offset, sort
2. WHERE clause is built dynamically based on filters
3. Total count is calculated with same filters
4. Paginated results are returned

5. Interactions
- Uses app/core/database.py for DB engine.
- Mounted by app/main.py.
- Serves data to Android remote layer (Chunk 1–3 endpoints).

6. Assumptions
- Schema tables sector_predictions and sector_sentiment_daily are populated.
- Snapshot date is daily, not real-time.
- Signal enum: UP, DOWN, NEUTRAL
- Confidence values are [0, 1]

7. Future Improvements
- Move SQL into service layer.
- Add response schema validation.
- Add caching for repeated snapshot requests with same filters.
- Add indices on (sector_id, date) and (signal, confidence) for faster filtering.
