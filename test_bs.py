import sys
from app.scrapers.News_Scrappers.business_standard_scraper import BusinessStandardScraper

scraper = BusinessStandardScraper()
# Test page 2 formats
urls = [
    "https://www.business-standard.com/markets/news/page-2",
    "https://www.business-standard.com/markets/news/page/2"
]

for url in urls:
    try:
        resp = scraper._get(url)
        print(f"URL: {url} -> Status: {resp.status_code}, Length: {len(resp.text)}")
    except Exception as e:
        print(f"URL: {url} -> Error: {e}")
