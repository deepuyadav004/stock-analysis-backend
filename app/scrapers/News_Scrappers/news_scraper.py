"""
news_scraper.py
---------------
Main entry point for the news scraping pipeline.

Responsibilities:
  1. Run all source scrapers (ET, MoneyControl, Business Standard, Livemint)
  2. Deduplicate articles by URL
  3. Tag each article to one or more sectors using keyword matching
  4. Return a sector-grouped mapping ready for sentiment analysis

Output format:
    {
        sector_name: [Article, Article, ...],
        ...
    }

Articles are NEVER stored to disk or DB — they live in memory only.
"""

import re
from collections import defaultdict
from datetime import date
from sqlalchemy import text
from app.core.database import engine

from app.scrapers.News_Scrappers.base_scraper import Article
from app.scrapers.News_Scrappers.business_standard_scraper import BusinessStandardScraper
from app.scrapers.News_Scrappers.economic_times_scraper import EconomicTimesScraper
from app.scrapers.News_Scrappers.livemint_scraper import LivemintScraper
from app.scrapers.News_Scrappers.moneycontrol_scraper import MoneyControlScraper
from app.models.SentimentAnalyzer import get_sentiment_analyzer


# ---------------------------------------------------------------------------
# Sector keyword dictionary
# Each sector maps to a list of case-insensitive keywords/phrases.
# An article is tagged to a sector if ANY keyword appears in its text.
# An article can be tagged to multiple sectors.
# ---------------------------------------------------------------------------
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Automobile and Auto Components": [
        "automobile", "auto sector", "auto component", "ev", "electric vehicle",
        "maruti", "tata motors", "bajaj auto", "hero motocorp", "mahindra",
        "hyundai", "ashok leyland", "motherson", "bosch", "tyre", "vehicle",
        "two wheeler", "commercial vehicle", "passenger vehicle", "auto ancillaries", "e-vehicle", "mobility",
    ],
    "Capital Goods": [
        "capital goods", "industrial machinery", "engineering goods", "defence equipment",
        "larsen and toubro", "lt", "siemens", "abb", "bharat forge", "bhel",
        "heavy electrical", "manufacturing equipment", "heavy machinery", "industrial equipment",
    ],
    "Chemicals": [
        "chemical", "specialty chemical", "petrochemical", "agrochemical", "caustic",
        "aarti industries", "deepak nitrite", "pidilite", "alkyl amines", "vinati organics",
        "fertilizer", "polymers", "resin", "speciality chemicals",
    ],
    "Construction": [
        "construction", "infrastructure project", "epc", "road project", "highway",
        "railway project", "metro project", "construction order", "contract award",
        "infrastructure development", "civil engineering", "building project",
    ],
    "Construction Materials": [
        "cement", "clinker", "ready mix concrete", "construction material", "tiles",
        "ultratech", "ambuja", "acc", "shree cement", "jk cement",
        "building materials", "paint", "glass", "asian paints", "berger paints",
    ],
    "Consumer Durables": [
        "consumer durable", "white goods", "home appliance", "ac sales", "refrigerator",
        "washing machine", "electronics retail", "voltas", "havells", "whirlpool",
        "consumer electronics", "smartphones", "wearables", "appliances",
    ],
    "Consumer Services": [
        "consumer services", "travel", "hospitality", "restaurant", "qsr", "ecommerce",
        "aviation", "hotel", "multiplex", "delivery platform", "easy trip", "zomato", "swiggy",
        "retail", "tourism", "quick commerce", "food delivery", "indigo",
    ],
    "Diversified": [
        "diversified", "conglomerate", "multi business", "holding company",
        "aditya birla group", "itc", "reliance industries", "godrej group", "conglomerate group",
    ],
    "Fast Moving Consumer Goods": [
        "fmcg", "fast moving consumer goods", "consumer staples", "packaged food",
        "beverages", "hindustan unilever", "hul", "itc", "nestle", "dabur", "marico",
        "personal care", "groceries", "fmcg sector", "britannia", "godrej consumer",
    ],
    "Financial Services": [
        "financial services", "bank", "nbfc", "rbi", "reserve bank", "credit", "loan",
        "insurance", "asset management", "brokerage", "mutual fund", "hdfc", "icici", "sbi",
        "fintech", "wealth management", "microfinance", "housing finance", "private equity", "kotak", "axis bank",
    ],
    "Forest Materials": [
        "forest materials", "paper", "pulp", "packaging board", "wood products",
        "jk paper", "west coast paper", "seshasayee paper", "ballarpur", "paperboard",
    ],
    "Healthcare": [
        "healthcare", "hospital", "diagnostics", "pharma", "drug", "medicine",
        "fda", "usfda", "clinical trial", "sun pharma", "cipla", "apollo hospitals",
        "biotech", "medical devices", "life sciences", "api", "dr reddy", "lupin",
    ],
    "Information Technology": [
        "information technology", "it services", "software", "digital", "cloud", "cyber",
        "artificial intelligence", "data center", "saas", "infosys", "tcs", "wipro", "hcl tech",
        "tech sector", "gen ai", "machine learning", "bpo", "kpo", "software development", "tech mahindra",
    ],
    "Media Entertainment & Publication": [
        "media", "entertainment", "publication", "broadcast", "tv network", "ott",
        "newspaper", "advertising revenue", "zee", "sun tv", "network18", "jagran",
        "streaming", "cinema", "box office", "radio", "pvr", "inox",
    ],
    "Metals & Mining": [
        "steel", "metal", "mining", "tata steel", "jsw steel", "hindalco", "vedanta",
        "aluminium", "copper", "iron ore", "zinc", "nickel", "coal india", "nmdc",
        "precious metals", "gold", "silver", "manganese", "jindal steel",
    ],
    "Oil Gas & Consumable Fuels": [
        "oil", "crude", "natural gas", "lng", "petroleum", "fuel", "refinery",
        "reliance", "ongc", "ioc", "bpcl", "hpcl", "opec", "consumable fuels",
        "energy sector", "oil exploration", "gas pipeline", "gail", "oil india",
    ],
    "Power": [
        "power", "electricity", "utility", "generation", "transmission", "distribution",
        "renewable", "solar", "wind energy", "ntpc", "tata power", "adani power",
        "green energy", "hydropower", "thermal power", "clean energy", "power grid",
    ],
    "Realty": [
        "realty", "real estate", "property", "housing", "dlf", "godrej properties",
        "oberoi realty", "prestige estates", "brigade", "home sales", "residential project",
        "commercial real estate", "township", "leasing", "macrotech", "lodha",
    ],
    "Services": [
        "services", "service sector", "outsourcing", "facility management", "logistics services",
        "professional services", "business services", "staffing", "security services",
    ],
    "Telecommunication": [
        "telecommunication", "telecom", "5g", "spectrum", "arpu", "broadband", "fiber",
        "airtel", "jio", "vodafone idea", "vi", "subscriber additions",
        "cellular", "telecom operator", "network provider", "bharti airtel",
    ],
    "Textiles": [
        "textiles", "garment", "apparel", "yarn", "fabric", "cotton", "spinning",
        "weaving", "export order", "arvind", "trident", "welspun",
        "synthetic yarn", "clothing", "textile export", "raymond",
    ],
    "Utilities": [
        "utilities", "water utility", "gas utility", "city gas distribution", "electric utility",
        "adani total gas", "igl", "mgl", "power grid", "distribution utility",
    ],
}


def _compile_patterns() -> dict[str, re.Pattern]:
    """Pre-compile keyword patterns for fast matching."""
    compiled: dict[str, re.Pattern] = {}
    for sector, keywords in SECTOR_KEYWORDS.items():
        # Escape special chars and join with | for OR matching.
        escaped = [re.escape(kw) for kw in keywords]
        compiled[sector] = re.compile(
            r"\b(?:" + "|".join(escaped) + r")\b",
            re.IGNORECASE,
        )
    return compiled


_SECTOR_PATTERNS: dict[str, re.Pattern] = _compile_patterns()


def _tag_article(article: Article) -> list[str]:
    """
    Return a list of sector names that match this article.
    Matching is done against (title + summary) combined text.
    Returns empty list if no sector matches.
    """
    text = article.text
    matched_sectors: list[str] = []
    for sector, pattern in _SECTOR_PATTERNS.items():
        if pattern.search(text):
            matched_sectors.append(sector)
    return matched_sectors


def _deduplicate(articles: list[Article]) -> list[Article]:
    """Remove articles with duplicate URLs (keep first seen)."""
    seen_urls: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        if article.url not in seen_urls:
            seen_urls.add(article.url)
            unique.append(article)
    return unique


def scrape_and_tag() -> dict[str, list[Article]]:
    """
    Run all scrapers, deduplicate, tag articles to sectors, and return
    a dict mapping sector name -> list of matching Article objects.

    This is the main function called by the sentiment pipeline.
    Nothing is written to DB or disk.
    """
    # 1. Collect raw articles from all sources.
    all_articles: list[Article] = []
    scrapers = [
        EconomicTimesScraper(),
        MoneyControlScraper(),
        LivemintScraper(),
    ]

    for scraper in scrapers:
        articles = scraper.scrape()
        all_articles.extend(articles)
        scraper.close()

    print(
        f"[NewsScraper] Total raw articles collected: {len(all_articles)}",
        flush=True,
    )

    # 2. Deduplicate by URL.
    unique_articles = _deduplicate(all_articles)
    print(
        f"[NewsScraper] After deduplication: {len(unique_articles)} unique articles",
        flush=True,
    )

    # 3. Tag each article to sectors.
    sector_map: dict[str, list[Article]] = defaultdict(list)
    untagged_count = 0

    for article in unique_articles:
        matched_sectors = _tag_article(article)
        if not matched_sectors:
            untagged_count += 1
            continue
        for sector in matched_sectors:
            sector_map[sector].append(article)

    # 4. Print summary.
    print(f"[NewsScraper] Untagged articles (no sector match): {untagged_count}", flush=True)
    for sector, sector_articles in sorted(sector_map.items()):
        print(
            f"[NewsScraper]   {sector}: {len(sector_articles)} articles",
            flush=True,
        )

    return dict(sector_map)


def scrape_and_tag_as_text() -> dict[str, list[str]]:
    """
    Convenience wrapper — same as scrape_and_tag() but returns plain strings
    (article.text) instead of Article objects. Useful for sentiment models
    that just need the raw text.

    Returns:
        { sector_name: ["headline1 summary1", "headline2 summary2", ...] }
    """
    sector_map = scrape_and_tag()
    return {
        sector: [article.text for article in articles]
        for sector, articles in sector_map.items()
    }

def scrape_analyze_and_report() -> dict:
    """
    Scrape all news, tag by sector, and run the FinBERT sentiment analyzer
    on the aggregated texts. Prints a detailed console report.
    """
    sector_texts = scrape_and_tag_as_text()
    analyzer = get_sentiment_analyzer()
    
    print("\n[SentimentAnalyzer] Starting sentiment analysis on scraped news (this may take a few minutes for all articles)...", flush=True)
    results = analyzer.analyze_sectors(sector_texts)
    
    print("\n" + "="*40)
    print("SECTOR SENTIMENT REPORT")
    print("="*40)
    for sector, data in sorted(results.items()):
        print(f"\n[{sector}] -> {data['label']} (Avg Score: {data['average_score']})")
        print(f"  Articles Analyzed: {data['article_count']}")
        print(f"  Breakdown: {data['breakdown']['positive']} Pos, {data['breakdown']['negative']} Neg, {data['breakdown']['neutral']} Neu")
    
    return results

def save_sentiment_to_db(results: dict) -> None:
    """
    Save the sentiment analysis results to the database (sector_sentiment_daily table).
    Handles mapping sector names to IDs and performs an upsert.
    """
    with engine.begin() as conn:
        # Load sector name -> id mapping
        sectors_res = conn.execute(text("SELECT id, name FROM sectors"))
        sector_name_to_id = {row["name"]: row["id"] for row in sectors_res.mappings()}
        
        today = date.today()
        
        for sector_name, data in results.items():
            sector_id = sector_name_to_id.get(sector_name)
            if not sector_id:
                print(f"[NewsScraper] Warning: Sector '{sector_name}' not found in DB. Skipping.")
                continue
            
            # Upsert into sector_sentiment_daily
            conn.execute(
                text("""
                    INSERT INTO sector_sentiment_daily (sector_id, date, avg_score, article_count)
                    VALUES (:sector_id, :date, :avg_score, :article_count)
                    ON CONFLICT (sector_id, date) 
                    DO UPDATE SET 
                        avg_score = EXCLUDED.avg_score,
                        article_count = EXCLUDED.article_count
                """),
                {
                    "sector_id": sector_id,
                    "date": today,
                    "avg_score": data["average_score"],
                    "article_count": data["article_count"]
                }
            )
        print(f"[NewsScraper] Successfully saved sentiment scores to DB for {len(results)} sectors.", flush=True)

def scrape_analyze_and_save() -> dict:
    """
    Full pipeline: Scrape, Tag, Analyze, and Save results to DB.
    """
    results = scrape_analyze_and_report()
    save_sentiment_to_db(results)
    return results


# ---------------------------------------------------------------------------
# CLI entry point — run this file directly to test the scraper
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--sentiment":
            print("Running news scraper WITH sentiment analysis...\n", flush=True)
            scrape_analyze_and_report()
        elif sys.argv[1] == "--save":
            print("Running news scraper WITH sentiment analysis and SAVING to DB...\n", flush=True)
            scrape_analyze_and_save()
    else:
        print("Running news scraper (pass --sentiment to also run sentiment analysis)...\n", flush=True)
        results = scrape_and_tag()

        print("\n=== RESULTS ===")
        for sector, articles in sorted(results.items()):
            print(f"\n[{sector}] — {len(articles)} articles")
            for i, article in enumerate(articles[:3], 1):   # Show first 3 per sector
                print(f"  {i}. [{article.source}] {article.title[:90]}")
            if len(articles) > 3:
                print(f"  ... and {len(articles) - 3} more")
