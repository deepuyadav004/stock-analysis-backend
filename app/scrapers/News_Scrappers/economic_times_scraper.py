"""
economic_times_scraper.py
--------------------------
Scrapes market news headlines from Economic Times markets section.
URL: https://economictimes.indiatimes.com/markets/stocks/news
"""

from bs4 import BeautifulSoup

from app.scrapers.News_Scrappers.base_scraper import Article, BaseScraper


class EconomicTimesScraper(BaseScraper):

    SOURCE_NAME = "Economic Times"
    _BASE_URL = "https://economictimes.indiatimes.com"
    _NEWS_URL = f"{_BASE_URL}/markets/stocks/news"
    REQUEST_DELAY = 2.5

    def fetch_headlines(self) -> list[Article]:
        articles: list[Article] = []
        page = 1

        while len(articles) < 50:
            if page == 1:
                page_url = self._NEWS_URL
            else:
                page_url = f"{self._BASE_URL}/markets/stocks/news/articlelist/msid-2146843,page-{page}.cms"

            try:
                print(f"[{self.SOURCE_NAME}] Fetching page {page}...", flush=True)
                response = self._get(page_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # ET renders news list as <div class="eachStory"> blocks.
                story_blocks = soup.select("div.eachStory")

                if not story_blocks:
                    break

                for block in story_blocks:
                    if len(articles) >= 50:
                        break

                    anchor = block.select_one("h3 a, h2 a, a")
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
                        
                        content_div = art_soup.select_one(".artText, .pageContent, article")
                        if content_div:
                            # Try paragraphs first
                            p_tags = content_div.find_all("p")
                            summary = " ".join([p.get_text(strip=True) for p in p_tags if len(p.get_text(strip=True)) > 20])
                            if not summary:
                                summary = content_div.get_text(separator=" ", strip=True)
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
