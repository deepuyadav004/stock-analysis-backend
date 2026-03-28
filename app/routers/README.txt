Module: API Routers

1. Purpose
Expose HTTP endpoints for backend clients.

2. Problem Solved
Provides stable entry points for mobile app data retrieval and health checks.

3. File Responsibilities
- home.py: Chunk 1 home snapshot endpoints.
- test.py: Lightweight service availability endpoint.
- __init__.py: Package marker.

4. Step-by-Step Flow
1. Route receives HTTP request.
2. Query params are validated.
3. SQL query is executed using shared engine.
4. Response is normalized into JSON payload.

5. Interactions
- Uses app/core/database.py for DB engine.
- Mounted by app/main.py.

6. Assumptions
- Schema tables sector_predictions and sector_sentiment_daily are populated.
- Snapshot date is daily, not real-time.

7. Future Improvements
- Move SQL into service layer.
- Add response schema validation.
- Add caching for repeated snapshot requests.
