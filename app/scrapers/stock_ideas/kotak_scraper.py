from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scrapers.stock_ideas.base_scraper import BaseStockIdeasScraper
from app.scrapers.stock_ideas.config import SOURCE_CONFIGS
from app.scrapers.stock_ideas.types import StockIdeaRecord
from app.scrapers.stock_ideas.utils import deduplicate_recommendations, save_recommendations


_DATE_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)


class KotakStockIdeasScraper(BaseStockIdeasScraper):
    source = SOURCE_CONFIGS["kotakneo"].key
    url = SOURCE_CONFIGS["kotakneo"].url

    def __init__(self) -> None:
        super().__init__()
        self.max_pages = SOURCE_CONFIGS["kotakneo"].max_pages

    def run(self) -> dict[str, int]:
        all_rows: list[StockIdeaRecord] = []
        current_url: str | None = self.url
        visited_urls: set[str] = set()

        for page_number in range(1, self.max_pages + 1):
            if not current_url or current_url in visited_urls:
                break

            visited_urls.add(current_url)
            html = self.fetch_page(current_url)
            rows = self.parse_recommendations(html)
            if not rows:
                break

            all_rows.extend(rows)
            current_url = self._find_next_page_url(html, current_url, page_number + 1)

        deduplicated = deduplicate_recommendations(all_rows)
        saved = save_recommendations(deduplicated)
        return {
            "parsed": len(all_rows),
            "deduplicated": len(deduplicated),
            "saved": saved,
        }

    def parse_recommendations(self, html: str) -> list[StockIdeaRecord]:
        soup = BeautifulSoup(html, "html.parser")
        candidates = soup.select("table tbody tr")
        records: list[StockIdeaRecord] = []

        for node in candidates:
            columns = [" ".join(td.get_text(" ", strip=True).split()) for td in node.select("td")]
            if len(columns) < 4:
                continue

            headline = columns[0]
            company_name = self._extract_company_name(headline)
            ticker = self._extract_ticker(headline)
            if not ticker:
                ticker = self._derive_ticker_from_name(company_name)

            recommendation = self._extract_recommendation(headline)
            status = self._extract_status(headline)
            cmp_price = columns[1] if len(columns) > 1 else None
            target_price = columns[2] if len(columns) > 2 else None
            market_price = columns[3] if len(columns) > 3 else None
            brief_reason = self._compose_rationale(status, target_price, cmp_price, market_price)

            if not ticker:
                continue

            records.append(
                {
                    "ticker": ticker,
                    "company_name": self.normalize_text(company_name) or ticker,
                    "call_type": self.normalize_call_type(recommendation),
                    "target_price": self.normalize_target_price(target_price),
                    "recommendation_date": self._parse_date(None),
                    "source": self.source,
                    "brief_rationale": self.normalize_text(brief_reason),
                }
            )

        return records

    def _extract_ticker(self, text: str) -> str | None:
        if not text:
            return None
        for candidate in re.findall(r"\b[A-Z]{2,15}\b", text.upper()):
            if candidate not in {"BUY", "SELL", "HOLD", "NSE", "BSE", "INR"}:
                return candidate
        return None

    def _derive_ticker_from_name(self, name: str | None) -> str | None:
        if not name:
            return None
        words = [w for w in re.findall(r"[A-Za-z]+", name.upper()) if len(w) > 1]
        if not words:
            return None
        return words[0][:15]

    def _extract_company_name(self, text: str) -> str:
        cleaned = re.sub(r"\([^)]*\)", "", text).strip()
        cleaned = re.sub(r"^[A-Z]\s+", "", cleaned)
        cleaned = re.sub(r"\b(Buy|Sell|Hold|Add|Reduce|Open|Closed)\b.*$", "", cleaned, flags=re.I).strip()
        return cleaned or text

    def _extract_recommendation(self, text: str) -> str | None:
        match = re.search(r"\b(Buy|Sell|Hold|Add|Reduce)\b", text, flags=re.I)
        if not match:
            return None
        value = match.group(1).lower()
        if value in {"add", "buy"}:
            return "BUY"
        if value in {"reduce", "sell"}:
            return "SELL"
        if value == "hold":
            return "HOLD"
        return None

    def _extract_status(self, text: str) -> str | None:
        match = re.search(r"\b(Open|Closed)\b", text, flags=re.I)
        return match.group(1).title() if match else None

    def _compose_rationale(
        self,
        status: str | None,
        target: str | None,
        cmp_price: str | None,
        market_price: str | None,
    ) -> str | None:
        parts: list[str] = []
        if status:
            parts.append(f"Status: {status}")
        if target:
            parts.append(f"Target: {target}")
        if cmp_price:
            parts.append(f"CMP: {cmp_price}")
        if market_price:
            parts.append(f"Market: {market_price}")
        return " | ".join(parts) if parts else None

    def _parse_date(self, value: str | None) -> date | None:
        if not value:
            return None
        text_value = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text_value, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def _find_next_page_url(self, html: str, current_url: str, next_page_number: int) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            "a[rel='next']",
            "a.next",
            ".pagination a.next",
            ".paging a.next",
            ".page-item.next a",
        ]
        for selector in selectors:
            anchor = soup.select_one(selector)
            if not anchor:
                continue
            href = (anchor.get("href") or "").strip()
            if href:
                return urljoin(current_url, href)

        for anchor in soup.select("a"):
            label = anchor.get_text(" ", strip=True).lower()
            if label in {"next", "next >", ">", "older"}:
                href = (anchor.get("href") or "").strip()
                if href:
                    return urljoin(current_url, href)

        # Fallback to path-based pagination used by Kotak recommendations pages.
        return re.sub(r"/\d+/?$", f"/{next_page_number}/", current_url)


def run() -> dict[str, int]:
    scraper = KotakStockIdeasScraper()
    return scraper.run()


if __name__ == "__main__":
    summary = run()
    print(
        "Kotak scrape complete: "
        f"parsed={summary['parsed']}, deduplicated={summary['deduplicated']}, saved={summary['saved']}"
    )
