"""
moneycontrol_scraper.py
-----------------------
Scrapes market news headlines from MoneyControl.
URL: https://www.moneycontrol.com/news/business/markets/
"""

from bs4 import BeautifulSoup

from app.scrapers.News_Scrappers.base_scraper import Article, BaseScraper


class MoneyControlScraper(BaseScraper):

    SOURCE_NAME = "MoneyControl"
    _BASE_URL = "https://www.moneycontrol.com"
    _NEWS_URL = f"{_BASE_URL}/news/business/markets/"
    REQUEST_DELAY = 0.5

    def fetch_headlines(self) -> list[Article]:
        articles: list[Article] = []

        for page in range(1, 6):
            if page == 1:
                page_url = self._NEWS_URL
            else:
                page_url = f"{self._NEWS_URL}page-{page}/"
                
            try:
                response = self._get(page_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # MoneyControl news listing uses <li class="clearfix"> items
                story_blocks = soup.select("li.clearfix")

                for block in story_blocks:
                    anchor = block.select_one("h2 a, h3 a, a")
                    if not anchor:
                        continue

                    title = anchor.get_text(separator=" ", strip=True)
                    # Filter out non-article links
                    if not title or "hello, login" in title.lower() or "hello login" in title.lower():
                        continue

                    href = anchor.get("href", "")
                    if not href or "javascript" in href.lower() or "login" in href.lower():
                        continue

                    url = href if href.startswith("http") else self._BASE_URL + href

                    summary = ""
                    # Fetch full article text
                    try:
                        art_response = self._get(url)
                        art_soup = BeautifulSoup(art_response.text, "html.parser")
                        
                        # Find the main article container
                        content_div = art_soup.select_one(".content_wrapper, .arti-flow, #article-main, .article_desc")
                        if content_div:
                            p_tags = content_div.find_all("p")
                            summary = " ".join([p.get_text(strip=True) for p in p_tags])
                        else:
                            p_tags = art_soup.find_all("p")
                            summary = " ".join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 50])
                    except Exception as e:
                        print(f"[{self.SOURCE_NAME}] Failed to fetch article ({url}): {e}", flush=True)

                    # Fallback to list summary if full article extraction failed
                    if not summary:
                        summary_tag = block.select_one("p")
                        summary = summary_tag.get_text(strip=True) if summary_tag else ""

                    articles.append(Article(
                        title=title,
                        summary=summary.strip(),
                        source=self.SOURCE_NAME,
                        url=url,
                    ))
            except Exception as e:
                print(f"[{self.SOURCE_NAME}] Failed to fetch page {page}: {e}", flush=True)

        return articles
