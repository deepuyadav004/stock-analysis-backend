from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import httpx

from app.scrapers.stock_ideas.config import DEFAULT_REQUEST_TIMEOUT_SECONDS, DEFAULT_USER_AGENT
from app.scrapers.stock_ideas.types import StockIdeaRecord
from app.scrapers.stock_ideas.utils import deduplicate_recommendations, save_recommendations


class BaseStockIdeasScraper(ABC):
    source: str
    url: str

    def __init__(self, timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_page(self, url: str | None = None) -> str:
        headers = {
            "user-agent": DEFAULT_USER_AGENT,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
        }
        target_url = url or self.url
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(target_url)
            response.raise_for_status()
            return response.text

    @abstractmethod
    def parse_recommendations(self, html: str) -> list[StockIdeaRecord]:
        """Parse source HTML into normalized stock idea rows."""

    def run(self) -> dict[str, int]:
        html = self.fetch_page()
        parsed = self.parse_recommendations(html)
        unique_rows = deduplicate_recommendations(parsed)
        inserted_or_updated = save_recommendations(unique_rows)
        return {
            "parsed": len(parsed),
            "deduplicated": len(unique_rows),
            "saved": inserted_or_updated,
        }

    @staticmethod
    def normalize_call_type(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().lower()
        if "buy" in normalized:
            return "BUY"
        if "sell" in normalized:
            return "SELL"
        if "hold" in normalized:
            return "HOLD"
        return None

    @staticmethod
    def normalize_target_price(value: str | int | float | Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        text_value = str(value).strip().replace(",", "")
        if not text_value:
            return None
        for token in ("INR", "Rs", "rs", "\u20b9"):
            text_value = text_value.replace(token, "")
        text_value = text_value.strip()
        try:
            return Decimal(text_value)
        except InvalidOperation:
            return None

    @staticmethod
    def normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None
