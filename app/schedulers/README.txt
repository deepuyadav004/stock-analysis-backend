Module: Daily Pipeline Scheduler

1. Purpose
Provide a reusable scheduler-facing entrypoint for the daily backend pipeline.

2. Problem Solved
Separates orchestration logic from CLI-only scripts so the same pipeline can be run by:
- local scripts
- API-triggered jobs
- deployment cron services (for example Vercel Cron)

3. File Responsibilities
- daily_pipeline.py: Contains run_daily_pipeline(), the single orchestration function for daily scrape, sentiment aggregation, feature preparation, and prediction persistence.

4. Step-by-Step Flow
1. Scrape financial news from configured sources.
2. Tag articles by sector and run FinBERT sentiment scoring.
3. Save sector sentiment into sector_sentiment_daily.
4. Build historical features for each sector.
5. Combine historical features with current-day sentiment.
6. Generate and store predictions in sector_predictions.

5. Interactions with Other Modules
- app/scrapers/News_Scrappers/news_scraper.py for scrape/analyze/save.
- app/models/FeatureBuilder for feature construction.
- app/models/PredictionModel for prediction and persistence.
- app/core/database.py for sector-id mapping query.

6. Assumptions
- Sector master data is already imported and available in sectors table.
- Database credentials are available through environment config.
- External news sources are reachable when the job runs.

7. Future Improvements
- Add execution telemetry (duration, failures, row counts) persisted to a job_runs table.
- Add idempotency safeguards for repeated same-day triggers.
- Add retry strategy around external scraper failures.

8. Weekly NSE Price Import Scheduler
Purpose:
- Run a weekly NSE OHLCV sync as a deployment cron job.

Files:
- nse_weekly_price_history.py: exposes run_nse_weekly_price_history() which imports last 7 days of NSE price data using a single 7-day API window.

Flow:
1. Cron trigger starts run_weekly_nse_price_history.py.
2. Script calls app.schedulers.nse_weekly_price_history.run_nse_weekly_price_history().
3. Scheduler calls import_nse_price_history(lookback_days=7, window_days=7).
4. Scraper fetches last-week price data and upserts into stock_prices.

9. Daily Stock Ideas Ingestion Scheduler
Purpose:
- Run recommendation ingestion from Moneycontrol, Kotak Neo, and Lemonn once per day.

Files:
- stock_ideas_daily.py: exposes run_daily_stock_ideas_ingestion() and executes all source scrapers with per-source fault isolation.
- ../run_stock_ideas_daily.py: lightweight CLI entrypoint to run stock ideas ingestion manually.

Flow:
1. Scheduler starts run_daily_stock_ideas_ingestion().
2. Moneycontrol scraper runs and returns parsed/deduplicated/saved counts.
3. Kotak Neo scraper runs and returns parsed/deduplicated/saved counts.
4. Lemonn scraper runs and returns parsed/deduplicated/saved counts.
5. Scheduler aggregates source summaries and prints final status (ok/partial).

10. Daily News Links Ingestion Scheduler
Purpose:
- Run daily headline-link ingestion for the News tab from ICICI Direct, Economic Times, and Moneycontrol.

Files:
- news_links_daily.py: exposes run_daily_news_links_ingestion() and delegates source scraping/upsert to news_links_ingestor.

Flow:
1. Scheduler starts run_daily_news_links_ingestion(target_count_per_source=50).
2. Ingestor runs all three source scrapers.
3. Each source scraper follows pagination and attempts to collect up to 50 items.
4. Records are deduplicated by (source, source_url) and upserted into news_articles.
5. Scheduler returns per-source and aggregate summary for logs/API response.
