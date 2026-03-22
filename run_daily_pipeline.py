from datetime import date
from sqlalchemy import text
from app.core.database import engine

from app.scrapers.News_Scrappers.news_scraper import scrape_analyze_and_save
from app.models.FeatureBuilder import SectorFeatureBuilder
from app.models.PredictionModel import SectorPredictionModel

def run_daily_pipeline():
    print(f"\n--- Starting Daily Prediction Pipeline for {date.today()} ---", flush=True)

    # 1. Scrape, Analyze today's news and save to sector_sentiment_daily
    print("\nPhase 1: Scraping and Sentiment Analysis...", flush=True)
    today_sentiment_results = scrape_analyze_and_save()
    
    # We need to map sector names to IDs for the model blocks
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, name FROM sectors"))
        name_to_id = {row["name"]: row["id"] for row in res.mappings()}

    today_sentiment_by_id = {}
    for name, data in today_sentiment_results.items():
        s_id = name_to_id.get(name)
        if s_id:
            today_sentiment_by_id[s_id] = data

    # 2. Build Features using yesterday's data from DB
    print("\nPhase 2: Building Features from Historical Data...", flush=True)
    builder = SectorFeatureBuilder()
    historical_features = builder.get_features_for_all_sectors()
    
    # 3. Generate Predictions using Today's Sentiment + Historical Features
    print("\nPhase 3: Generating Predictions...", flush=True)
    model = SectorPredictionModel()
    model_inputs = builder.prepare_model_input(historical_features, today_sentiment_by_id)
    
    predictions_made = 0
    for item in model_inputs:
        s_id = item["sector_id"]
        vector = item["input_vector"]
        
        prediction = model.predict(vector)
        model.save_prediction(s_id, prediction)
        predictions_made += 1
        
    print(f"\n--- Pipeline Complete: Generated predictions for {predictions_made} sectors ---", flush=True)

if __name__ == "__main__":
    run_daily_pipeline()
