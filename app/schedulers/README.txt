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
