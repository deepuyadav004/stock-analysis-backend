from __future__ import annotations

import json
from datetime import date, datetime

import httpx

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


class LemonnStockIdeasScraper(BaseStockIdeasScraper):
    source = SOURCE_CONFIGS["lemonn"].key
    url = SOURCE_CONFIGS["lemonn"].url
    api_url = "https://lemonn.co.in/api/get-lemonn-recommendation"

    def __init__(self) -> None:
        super().__init__()
        self.max_pages = SOURCE_CONFIGS["lemonn"].max_pages

    def run(self) -> dict[str, int]:
        all_rows: list[StockIdeaRecord] = []
        seen_page_signatures: set[tuple[str, ...]] = set()

        for page_number in range(1, self.max_pages + 1):
            payload = self._fetch_recommendations_page(page_number)
            rows = self.parse_recommendations(payload)
            if not rows:
                break

            page_signature = tuple(sorted({row["ticker"] for row in rows}))
            if page_signature in seen_page_signatures:
                break

            seen_page_signatures.add(page_signature)
            all_rows.extend(rows)

        deduplicated = deduplicate_recommendations(all_rows)
        saved = save_recommendations(deduplicated)
        return {
            "parsed": len(all_rows),
            "deduplicated": len(deduplicated),
            "saved": saved,
        }

    def parse_recommendations(self, payload_text: str) -> list[StockIdeaRecord]:
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return []

        entries = self._extract_entries(payload)
        records: list[StockIdeaRecord] = []

        for entry in entries:
            ticker = self._pick_str(entry, "symbol", "ticker", "stockSymbol")
            sym_obj = entry.get("symObj") if isinstance(entry, dict) else None
            if not ticker and isinstance(sym_obj, dict):
                ticker = self._pick_str(sym_obj, "symbol", "ticker", "streamSym")
            if not ticker:
                continue

            company_name = self._pick_str(entry, "company_name", "companyName", "name", "compName")
            if not company_name and isinstance(sym_obj, dict):
                company_name = self._pick_str(sym_obj, "compName", "companyName", "name")

            recommendation = self._pick_str(entry, "recommendation", "rating", "call")
            target_value = self._pick_str(
                entry,
                "target_price",
                "targetPrice",
                "target",
                "tgt",
                "priceTarget",
            )
            recommendation_date = self._parse_date(
                self._pick_str(
                    entry,
                    "recommendation_date",
                    "recommendationDate",
                    "date",
                    "updatedAt",
                    "createdAt",
                )
            )
            rationale = self._pick_str(entry, "rationale", "reason", "summary", "description")
            if not rationale:
                predicted_profit = self._pick_str(entry, "predicted_profit")
                accuracy = self._pick_str(entry, "accuracy")
                notes = [x for x in [predicted_profit, accuracy and f"Accuracy {accuracy}%"] if x]
                rationale = " | ".join(notes) if notes else None

            records.append(
                {
                    "ticker": ticker.upper(),
                    "company_name": self.normalize_text(company_name) or ticker.upper(),
                    "call_type": self.normalize_call_type(recommendation),
                    "target_price": self.normalize_target_price(target_value),
                    "recommendation_date": recommendation_date,
                    "source": self.source,
                    "brief_rationale": self.normalize_text(rationale),
                }
            )

        return records

    def _fetch_recommendations_page(self, page_number: int) -> str:
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.5",
            "content-type": "application/json",
            "origin": "https://lemonn.co.in",
            "referer": self.url,
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "x-encrypt": "false",
        }
        # Keep payload permissive because endpoint may ignore unknown pagination keys.
        body = {
            "page": page_number,
            "pageNo": page_number,
            "pageno": page_number,
        }
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.post(self.api_url, json=body)
            response.raise_for_status()
            return response.text

    def _extract_entries(self, payload: object) -> list[dict]:
        if not isinstance(payload, dict):
            return []

        current: object = payload
        for key in ("data", "response", "data"):
            if isinstance(current, dict) and key in current:
                current = current.get(key)

        if not isinstance(current, dict):
            return []

        rows: list[dict] = []
        for bucket in ("open", "closed", "all", "recommendations", "items"):
            value = current.get(bucket)
            if isinstance(value, list):
                rows.extend([item for item in value if isinstance(item, dict)])
        return rows

    def _pick_str(self, item: object, *keys: str) -> str | None:
        if not isinstance(item, dict):
            return None
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            text_value = str(value).strip()
            if text_value:
                return text_value
        return None

    def _parse_date(self, value: str | None) -> date | None:
        if not value:
            return None
        text_value = value.strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text_value, fmt).date()
            except ValueError:
                continue

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
            try:
                return datetime.strptime(text_value, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text_value.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def run() -> dict[str, int]:
    scraper = LemonnStockIdeasScraper()
    return scraper.run()


if __name__ == "__main__":
    summary = run()
    print(
        "Lemonn scrape complete: "
        f"parsed={summary['parsed']}, deduplicated={summary['deduplicated']}, saved={summary['saved']}"
    )
