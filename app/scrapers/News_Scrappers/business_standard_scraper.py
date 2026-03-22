"""
business_standard_scraper.py
-----------------------------
Scrapes market news headlines from Business Standard.
URL: https://www.business-standard.com/markets
"""

from bs4 import BeautifulSoup

from app.scrapers.News_Scrappers.base_scraper import Article, BaseScraper


class BusinessStandardScraper(BaseScraper):

    SOURCE_NAME = "Business Standard"
    _BASE_URL = "https://www.business-standard.com"
    _NEWS_URL = f"{_BASE_URL}/markets"
    REQUEST_DELAY = 2.5

    def fetch_headlines(self) -> list[Article]:
        response = self._get(self._NEWS_URL)
        soup = BeautifulSoup(response.text, "html.parser")
        articles: list[Article] = []

        # Business Standard news listing cards contain <a> headline links
        # within article or card wrapper elements.
        story_blocks = soup.select("div.listing-txt, article, div.card-body")

        for block in story_blocks:
            anchor = block.select_one("h2 a, h3 a, h4 a, a")
            if not anchor:
                continue

            title = anchor.get_text(separator=" ", strip=True)
            if not title or len(title) < 10:
                continue

            href = anchor.get("href", "")
            url = href if href.startswith("http") else self._BASE_URL + href

            summary_tag = block.select_one("p")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""

            articles.append(Article(
                title=title,
                summary=summary,
                source=self.SOURCE_NAME,
                url=url,
            ))

        return articles
