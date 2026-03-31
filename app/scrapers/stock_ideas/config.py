from dataclasses import dataclass


DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class SourceConfig:
    key: str
    display_name: str
    url: str
    max_pages: int = 10


SOURCE_CONFIGS: dict[str, SourceConfig] = {
    "moneycontrol": SourceConfig(
        key="moneycontrol",
        display_name="Moneycontrol",
        url="https://www.moneycontrol.com/stocks/marketstats/recommendations/index.php",
        max_pages=20,
    ),
    "kotakneo": SourceConfig(
        key="kotakneo",
        display_name="Kotak Neo",
        url="https://www.kotakneo.com/stock-research-recommendations/equity/longterm/1/",
        max_pages=5,
    ),
    "lemonn": SourceConfig(
        key="lemonn",
        display_name="Lemonn",
        url="https://lemonn.co.in/stock-recommendation",
        max_pages=5,
    ),
}
