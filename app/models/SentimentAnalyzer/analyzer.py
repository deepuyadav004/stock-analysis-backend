from transformers import pipeline

class SectorSentimentAnalyzer:
    def __init__(self):
        # FinBERT model from ProsusAI is specialized for financial sentiment
        # Output labels: "positive", "negative", "neutral"
        print("Loading FinBERT model (this may take a moment the first time)...", flush=True)
        self.pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")

    def analyze_text(self, text: str) -> dict:
        """
        Analyze a single text string and return its sentiment label and score.
        FinBERT limits tokens to 512, so we truncate if necessary.
        """
        try:
            # We use truncation=True to handle long texts
            res = self.pipeline(text, truncation=True, max_length=512)[0]
            # res looks like {'label': 'positive', 'score': 0.85}
            return {
                "label": res["label"],
                "score": res["score"]
            }
        except Exception as e:
            return {"label": "neutral", "score": 0.0, "error": str(e)}

    def analyze_sectors(self, sector_data: dict[str, list[str]]) -> dict[str, dict]:
        """
        Takes a mapping of sector names to lists of article texts.
        Returns a mapping of sector names to their aggregated sentiment scores.
        """
        results = {}
        for sector, texts in sector_data.items():
            if not texts:
                continue
            
            # Tally up scores
            counts = {"positive": 0, "negative": 0, "neutral": 0}
            total_score = 0.0
            
            for text in texts:
                sentiment = self.analyze_text(text)
                label = sentiment["label"]
                counts[label] += 1
                
                # To calculate an overall scalar score, we could treat positive as +1 * score, 
                # negative as -1 * score, and neutral as 0.
                if label == "positive":
                    total_score += sentiment["score"]
                elif label == "negative":
                    total_score -= sentiment["score"]
                # neutral contributes 0 to total_score
                
            article_count = len(texts)
            avg_score = total_score / article_count if article_count > 0 else 0.0
            
            # Thresholds for Bullish/Bearish
            if avg_score > 0.05:
                overall_label = "Bullish"
            elif avg_score < -0.05:
                overall_label = "Bearish"
            else:
                overall_label = "Neutral"

            results[sector] = {
                "average_score": round(avg_score, 3),
                "label": overall_label,
                "article_count": article_count,
                "breakdown": counts
            }
            
        return results

# Singleton instance to avoid reloading the model multiple times during a server run
_analyzer_instance = None

def get_sentiment_analyzer() -> SectorSentimentAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SectorSentimentAnalyzer()
    return _analyzer_instance
