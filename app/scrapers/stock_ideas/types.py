from datetime import date
from decimal import Decimal
from typing import TypedDict


class StockIdeaRecord(TypedDict):
    ticker: str
    company_name: str
    call_type: str | None
    target_price: Decimal | None
    recommendation_date: date | None
    source: str
    brief_rationale: str | None
