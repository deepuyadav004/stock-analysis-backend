from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class NewsArticleRecord(TypedDict):
    source: str
    source_url: str
    headline: str
    published_at: datetime | None
