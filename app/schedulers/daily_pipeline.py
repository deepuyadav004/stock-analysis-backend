from datetime import date

from sqlalchemy import text

from app.core.database import engine
from app.models.FeatureBuilder import SectorFeatureBuilder
from app.models.PredictionModel import SectorPredictionModel
from app.scrapers.News_Scrappers.news_scraper import scrape_analyze_and_save


def run_daily_pipeline() -> int:
    """Run scrape -> feature build -> prediction pipeline and return prediction count."""
    print(f"\n--- Starting Daily Prediction Pipeline for {date.today()} ---", flush=True)

    # 1. Scrape and analyze today's news, then save to sector_sentiment_daily.
    print("\nPhase 1: Scraping and Sentiment Analysis...", flush=True)
    today_sentiment_results = scrape_analyze_and_save()

    # Map sector names from sentiment output to sector IDs used by model pipeline.
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, name FROM sectors"))
        name_to_id = {row["name"]: row["id"] for row in res.mappings()}

    today_sentiment_by_id: dict[int, dict] = {}
    for name, data in today_sentiment_results.items():
        sector_id = name_to_id.get(name)
        if sector_id:
            today_sentiment_by_id[sector_id] = data

    # 2. Build model features from historical data.
    print("\nPhase 2: Building Features from Historical Data...", flush=True)
    builder = SectorFeatureBuilder()
    historical_features = builder.get_features_for_all_sectors()

    # 3. Generate predictions for all sectors and persist results.
    print("\nPhase 3: Generating Predictions...", flush=True)
    model = SectorPredictionModel()
    model_inputs = builder.prepare_model_input(historical_features, today_sentiment_by_id)

    predictions_made = 0
    for item in model_inputs:
        sector_id = item["sector_id"]
        vector = item["input_vector"]

        prediction = model.predict(vector)
        model.save_prediction(sector_id, prediction)
        predictions_made += 1

    print(
        f"\n--- Pipeline Complete: Generated predictions for {predictions_made} sectors ---",
        flush=True,
    )
    return predictions_made
