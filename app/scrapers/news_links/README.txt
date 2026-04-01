Module: News Links Scrapers

1. Module Purpose
Collect latest headline links from configured external sources and persist them into news_articles.

2. Problem Solved
Provides a single, repeatable ingestion path for the News tab so the app can show source headlines and redirect users to original sites.

3. File Responsibilities
- icicidirect_blog_scraper.py: Scrapes ICICI Direct equity blog pages with pagination.
- economic_times_expert_views_scraper.py: Scrapes Economic Times expert-views pages with pagination.
- moneycontrol_recommendations_scraper.py: Scrapes Moneycontrol recommendations pages with pagination.
- news_links_ingestor.py: Runs all source scrapers, deduplicates, and upserts into news_articles.
- utils.py: Shared HTTP fetch, URL normalization, date parsing, and next-page helpers.
- types.py: Typed schema for normalized news article records.

4. Step-by-Step Flow
1. Ingestor calls each source scraper.
2. Each scraper follows source pagination and tries to collect up to 50 latest articles.
3. Scrapers stop when target is reached, no next page exists, or page yields no new links.
4. Ingestor deduplicates by (source, source_url).
5. Ingestor upserts into news_articles using ON CONFLICT (source, source_url).

5. Interactions with Other Modules
- app/core/database.py for SQLAlchemy engine and transaction handling.
- app/schedulers for periodic execution.
- app/routers/jobs.py for manual trigger endpoints.

6. Assumptions
- news_articles table exists with unique index on (source, source_url).
- External source markup can change; selectors may need periodic refresh.
- published_at may be absent; null values are allowed.

7. Future Improvements
- Add source-specific parser tests with fixture HTML snapshots.
- Add retry/backoff for transient HTTP failures.
- Add telemetry persistence for per-run source stats.
