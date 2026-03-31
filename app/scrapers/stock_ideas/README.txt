Module: Stock Ideas Scrapers

1. Module Purpose
Provide reusable scraping base utilities for collecting stock recommendation ideas from multiple sources and storing only common fields.

2. Problem Solved
Standardizes parser output and DB persistence so source-specific scrapers can stay small and focused on extraction logic.

3. File Responsibilities
- __init__.py: Public exports for scraper base and persistence helpers.
- config.py: Source URLs and request defaults (timeout, user agent).
- types.py: Shared typed record for normalized recommendation rows.
- base_scraper.py: Abstract scraper contract (fetch, parse, run, normalize helpers).
- utils.py: Deduplication and DB save logic for stock_ideas_recommendations.

4. Step-by-Step Flow
1. Source scraper extends BaseStockIdeasScraper with source and url.
2. run() fetches HTML and calls parse_recommendations().
3. Parser returns normalized StockIdeaRecord rows.
4. deduplicate_recommendations() removes repeated rows by ticker+source+date.
5. save_recommendations() updates existing rows or inserts new ones.

5. Interactions with Other Modules
- app/core/database.py provides SQLAlchemy engine for persistence.
- app/schedulers will trigger each source scraper's run() method.
- app/routers/ideas.py will read from stock_ideas_recommendations.

6. Assumptions
- DB table stock_ideas_recommendations already exists.
- Source field values are one of: moneycontrol, kotakneo, lemonn.
- recommendation_date can be null for some sources.

7. Future Improvements
- Replace row-by-row update/insert with bulk merge for large daily volumes.
- Add per-source parser health metrics and failure counters.
- Add optional fetched_at field in DB when ingestion timing is needed.
