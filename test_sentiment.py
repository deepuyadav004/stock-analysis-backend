import json
from app.models.SentimentAnalyzer import get_sentiment_analyzer

def test():
    analyzer = get_sentiment_analyzer()
    
    # Dummy data simulating what the scraper would output
    sample_data = {
        "Automobile": [
            "Maruti Suzuki reports a 15% increase in sales this quarter.",
            "Semiconductor shortage disrupts auto manufacturing lines.",
            "EV adoption grows steadily in urban areas."
        ],
        "Banking": [
            "RBI increases repo rate by 50 basis points.",
            "SBI posts record quarterly profits driven by loan growth.",
            "Market worries about rising NPAs in private banks."
        ]
    }
    
    print("Running sentiment analysis on sample data...")
    results = analyzer.analyze_sectors(sample_data)
    
    print("\nResults:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test()
