from datetime import date, timedelta
from sqlalchemy import text
from app.core.database import engine

class SectorFeatureBuilder:
    def __init__(self, target_date: date = None):
        # We target today's prediction, so features come from yesterday
        self.target_date = target_date or date.today()
        self.feature_date = self.target_date - timedelta(days=1)

    def get_features_for_all_sectors(self) -> dict:
        """
        Fetches yesterday's sentiment and predictions for all sectors.
        Returns a dict: { sector_id: { 'prev_sentiment': 0.5, 'prev_prediction': 'UP' } }
        """
        features = {}
        
        with engine.connect() as conn:
            # 1. Fetch yesterday's sentiment
            sentiment_query = text("""
                SELECT sector_id, avg_score, article_count 
                FROM sector_sentiment_daily 
                WHERE date = :feature_date
            """)
            sentiment_res = conn.execute(sentiment_query, {"feature_date": self.feature_date})
            for row in sentiment_res.mappings():
                s_id = row["sector_id"]
                features[s_id] = {
                    "prev_sentiment_score": float(row["avg_score"]),
                    "prev_article_count": row["article_count"],
                    "prev_prediction": "NEUTRAL",  # Default if not found
                    "prev_confidence": 0.0
                }
            
            # 2. Fetch yesterday's predictions
            pred_query = text("""
                SELECT sector_id, signal, confidence 
                FROM sector_predictions 
                WHERE date = :feature_date
            """)
            pred_res = conn.execute(pred_query, {"feature_date": self.feature_date})
            for row in pred_res.mappings():
                s_id = row["sector_id"]
                if s_id not in features:
                    # In case we had a prediction but no sentiment (unlikely but safe)
                    features[s_id] = {
                        "prev_sentiment_score": 0.0,
                        "prev_article_count": 0,
                    }
                features[s_id]["prev_prediction"] = row["signal"]
                features[s_id]["prev_confidence"] = float(row["confidence"]) if row["confidence"] else 0.5

        return features

    def prepare_model_input(self, features: dict, current_sentiment: dict) -> list:
        """
        Combines yesterday's features with today's sentiment for the model.
        current_sentiment: { sector_id: { 'average_score': 0.8, 'article_count': 5 } }
        """
        model_inputs = []
        for s_id, today_data in current_sentiment.items():
            prev = features.get(s_id, {
                "prev_sentiment_score": 0.0,
                "prev_article_count": 0,
                "prev_prediction": "NEUTRAL",
                "prev_confidence": 0.5
            })
            
            # This list will be fed to the ML model (e.g., Logistic Regression or XGBoost)
            # Order: [Today's Sentiment, Prev Sentiment, Prev Prediction (encoded), Prev Confidence]
            
            # Encoding Prediction: UP=1, DOWN=-1, NEUTRAL=0
            pred_map = {"UP": 1, "DOWN": -1, "NEUTRAL": 0}
            encoded_pred = pred_map.get(prev["prev_prediction"], 0)
            
            model_inputs.append({
                "sector_id": s_id,
                "input_vector": [
                    float(today_data["average_score"]),
                    prev["prev_sentiment_score"],
                    encoded_pred,
                    prev["prev_confidence"]
                ]
            })
            
        return model_inputs
