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


class MoneycontrolStockIdeasScraper(BaseStockIdeasScraper):
    source = SOURCE_CONFIGS["moneycontrol"].key
    url = SOURCE_CONFIGS["moneycontrol"].url

    def __init__(self) -> None:
        super().__init__()
        self.max_pages = SOURCE_CONFIGS["moneycontrol"].max_pages

    def run(self) -> dict[str, int]:
        all_rows: list[StockIdeaRecord] = []
        current_url: str | None = self.url
        visited_urls: set[str] = set()

        for _ in range(self.max_pages):
            if not current_url or current_url in visited_urls:
                break

            visited_urls.add(current_url)
            html = self.fetch_page(current_url)
            rows = self.parse_recommendations(html)
            if not rows:
                break

            all_rows.extend(rows)
            current_url = self._find_next_page_url(html, current_url)

        deduplicated = deduplicate_recommendations(all_rows)
        saved = save_recommendations(deduplicated)
        return {
            "parsed": len(all_rows),
            "deduplicated": len(deduplicated),
            "saved": saved,
        }

    def parse_recommendations(self, html: str) -> list[StockIdeaRecord]:
        soup = BeautifulSoup(html, "html.parser")
        candidates = self._find_candidate_nodes(soup)
        records: list[StockIdeaRecord] = []

        for node in candidates:
            company_text = self._extract_by_selectors(
                node,
                [
                    ".company_name",
                    ".stock_name",
                    ".stock-name",
                    "[data-company-name]",
                    "h2",
                    "h3",
                    "h4",
                ],
            )
            ticker = self._extract_ticker(company_text or "")
            if not ticker:
                continue

            call_text = self._extract_by_selectors(
                node,
                [
                    ".recommendation",
                    ".rating",
                    ".call",
                    "[data-rating]",
                    "[data-recommendation]",
                ],
            )
            target_text = self._extract_by_selectors(
                node,
                [
                    ".target_price",
                    ".target-price",
                    ".target",
                    "[data-target-price]",
                ],
            )
            date_text = self._extract_by_selectors(
                node,
                [
                    ".date",
                    ".published-date",
                    ".publish-date",
                    "time",
                    "[datetime]",
                ],
            )
            rationale = self._extract_by_selectors(
                node,
                [
                    ".rationale",
                    ".summary",
                    ".description",
                    "p",
                ],
            )

            record: StockIdeaRecord = {
                "ticker": ticker,
                "company_name": self._extract_company_name(company_text or ticker),
                "call_type": self.normalize_call_type(call_text),
                "target_price": self.normalize_target_price(target_text),
                "recommendation_date": self._parse_date(date_text),
                "source": self.source,
                "brief_rationale": self.normalize_text(rationale),
            }
            records.append(record)

        return records

    def _find_candidate_nodes(self, soup: BeautifulSoup) -> list:
        selectors = [
            "table tbody tr",
            ".recommendation-card",
            ".stock-card",
            ".idea-card",
            "article",
        ]
        for selector in selectors:
            nodes = soup.select(selector)
            if nodes:
                return nodes
        return []

    def _extract_by_selectors(self, node, selectors: list[str]) -> str | None:
        for selector in selectors:
            found = node.select_one(selector)
            if not found:
                continue
            if selector == "[datetime]":
                value = found.get("datetime")
                if value:
                    return value.strip()
            text = found.get_text(" ", strip=True)
            if text:
                return text
        text = node.get_text(" ", strip=True)
        return text or None

    def _extract_ticker(self, text: str) -> str | None:
        if not text:
            return None
        for candidate in re.findall(r"\b[A-Z]{2,15}\b", text.upper()):
            if candidate not in {"BUY", "SELL", "HOLD", "NSE", "BSE", "INR"}:
                return candidate
        return None

    def _extract_company_name(self, text: str) -> str:
        cleaned = re.sub(r"\([^)]*\)", "", text).strip()
        return cleaned or text

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

    def _find_next_page_url(self, html: str, current_url: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")

        selectors = [
            "a[rel='next']",
            "a.next",
            ".pagination a.next",
            ".paging a.next",
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

        return None


def run() -> dict[str, int]:
    scraper = MoneycontrolStockIdeasScraper()
    return scraper.run()


if __name__ == "__main__":
    summary = run()
    print(
        "Moneycontrol scrape complete: "
        f"parsed={summary['parsed']}, deduplicated={summary['deduplicated']}, saved={summary['saved']}"
    )
