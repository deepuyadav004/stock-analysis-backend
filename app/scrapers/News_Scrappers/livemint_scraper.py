"""
livemint_scraper.py
-------------------
Scrapes market news headlines from Livemint.
URL: https://www.livemint.com/market
"""

from bs4 import BeautifulSoup

from app.scrapers.News_Scrappers.base_scraper import Article, BaseScraper


class LivemintScraper(BaseScraper):

    SOURCE_NAME = "Livemint"
    _BASE_URL = "https://www.livemint.com"
    _NEWS_URL = f"{_BASE_URL}/market/stock-market-news"
    REQUEST_DELAY = 1.0

    def fetch_headlines(self) -> list[Article]:
        articles: list[Article] = []
        page = 1

        while len(articles) < 100:
            if page == 1:
                page_url = self._NEWS_URL
            else:
                page_url = f"{self._NEWS_URL}/page-{page}/"

            try:
                print(f"[{self.SOURCE_NAME}] Fetching page {page}...", flush=True)
                response = self._get(page_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # Livemint uses headline list items with <h2> or <h3> containing <a> tags.
                story_blocks = soup.select(
                    "div.listingNew, div.headline, li.item, div.storyList, div.open-list, div.cardContainer, div.leftPanelSection"
                )

                if not story_blocks:
                    break

                for block in story_blocks:
                    if len(articles) >= 100:
                        break
                        
                    anchor = block.select_one("h2 a, h3 a, h1 a, a")
                    if not anchor:
                        continue

                    title = anchor.get_text(separator=" ", strip=True)
                    if not title or len(title) < 10:
                        continue

                    href = anchor.get("href", "")
                    url = href if href.startswith("http") else self._BASE_URL + href

                    summary = ""
                    # Fetch full article text
                    try:
                        art_response = self._get(url)
                        art_soup = BeautifulSoup(art_response.text, "html.parser")
                        
                        # Livemint's main article div often has class 'storyPage_storyContent' or 'mainArea'
                        content_div = art_soup.select_one(".storyPage_storyContent, .mainArea, .paywall, #mainArea")
                        if content_div:
                            p_tags = content_div.find_all("p")
                            summary = " ".join([p.get_text(strip=True) for p in p_tags])
                        else:
                            p_tags = art_soup.find_all("p")
                            summary = " ".join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 50])
                    except Exception as e:
                        print(f"[{self.SOURCE_NAME}] Failed to fetch article ({url}): {e}", flush=True)

                    if not summary:
                        summary_tag = block.select_one("p")
                        summary = summary_tag.get_text(strip=True) if summary_tag else ""

                    articles.append(Article(
                        title=title,
                        summary=summary.strip(),
                        source=self.SOURCE_NAME,
                        url=url,
                    ))

                page += 1
            except Exception as e:
                print(f"[{self.SOURCE_NAME}] Failed to fetch page {page}: {e}", flush=True)
                break

        return articles
