"""
News Scrapper package.

Public API:
    from app.scrapers.News_Scrappers.news_scraper import scrape_and_tag
    from app.scrapers.News_Scrappers.news_scraper import scrape_and_tag_as_text
"""

from app.scrapers.News_Scrappers.news_scraper import scrape_and_tag, scrape_and_tag_as_text

__all__ = ["scrape_and_tag", "scrape_and_tag_as_text"]
