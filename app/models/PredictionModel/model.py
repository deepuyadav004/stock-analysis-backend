from datetime import date
from sqlalchemy import text
from app.core.database import engine

class SectorPredictionModel:
    def __init__(self, model_version: str = "1.0-RuleBased"):
        self.model_version = model_version

    def predict(self, feature_vector: list) -> dict:
        """
        Takes a feature vector [today_sentiment, prev_sentiment, prev_prediction_encoded, prev_confidence]
        Returns a dict: { 'signal': 'UP'|'DOWN'|'NEUTRAL', 'confidence': float }
        
        Currently implemented as a weighted rule-based model.
        Higher weights on today's sentiment, but influenced by yesterday's momentum.
        """
        today_sent, prev_sent, prev_pred_enc, prev_conf = feature_vector
        
        # Simple weighted sum
        # Today's news is 70% weight, Yesterday's sentiment is 20%, Yesterday's prediction is 10%
        score = (today_sent * 0.7) + (prev_sent * 0.2) + (prev_pred_enc * prev_conf * 0.1)
        
        if score > 0.1:
            signal = "UP"
        elif score < -0.1:
            signal = "DOWN"
        else:
            signal = "NEUTRAL"
            
        return {
            "signal": signal,
            "confidence": min(abs(score) * 2, 1.0) # Scaling score to 0-1 range for confidence
        }

    def save_prediction(self, sector_id: int, prediction: dict, target_date: date = None) -> None:
        """
        Saves the model prediction to the sector_predictions table.
        """
        if target_date is None:
            target_date = date.today()
            
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO sector_predictions (sector_id, date, signal, confidence, model_version)
                    VALUES (:sector_id, :date, :signal, :confidence, :model_version)
                    ON CONFLICT (sector_id, date)
                    DO UPDATE SET
                        signal = EXCLUDED.signal,
                        confidence = EXCLUDED.confidence,
                        model_version = EXCLUDED.model_version
                """),
                {
                    "sector_id": sector_id,
                    "date": target_date,
                    "signal": prediction["signal"],
                    "confidence": prediction["confidence"],
                    "model_version": self.model_version
                }
            )
