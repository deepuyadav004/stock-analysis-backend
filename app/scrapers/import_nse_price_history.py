import argparse
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import engine


REPORT_URL = "https://www.nseindia.com/report-detail/eq_security"
API_URL = "https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData"
PAGE_HEADERS = [
    (
        "user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    ),
    (
        "accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8",
    ),
    ("accept-language", "en-US,en;q=0.9"),
    ("referer", REPORT_URL),
]
API_HEADERS = [
    ("accept", "*/*"),
    ("accept-language", "en-US,en;q=0.9"),
    ("priority", "u=1, i"),
    ("referer", REPORT_URL),
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("sec-fetch-dest", "empty"),
    ("sec-fetch-mode", "cors"),
    ("sec-fetch-site", "same-origin"),
    ("sec-gpc", "1"),
    (
        "user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    ),
]


def _format_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remaining_seconds = divmod(int(seconds), 60)
    hours, remaining_minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
    return f"{remaining_minutes}m {remaining_seconds}s"


def _format_nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def _parse_trade_date(row: dict[str, Any]) -> date:
    timestamp = row.get("mTIMESTAMP")
    if isinstance(timestamp, str) and timestamp:
        return datetime.strptime(timestamp, "%d-%b-%Y").date()

    iso_timestamp = row.get("CH_TIMESTAMP")
    if isinstance(iso_timestamp, str) and iso_timestamp:
        return datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00")).date()

    raise ValueError(f"Missing trade date in row: {row}")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _int_or_zero(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _iter_year_windows(end_date: date, years: int) -> list[tuple[date, date]]:
    start_date = end_date.replace(year=end_date.year - years)
    windows: list[tuple[date, date]] = []
    cursor = start_date

    while cursor <= end_date:
        next_year = cursor.replace(year=cursor.year + 1)
        window_end = min(next_year - timedelta(days=1), end_date)
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)

    return windows


def _make_nse_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = PAGE_HEADERS
    print("Bootstrapping NSE session...", flush=True)
    print(f"Opening {REPORT_URL}", flush=True)
    with opener.open(REPORT_URL, timeout=40):
        pass
    opener.addheaders = API_HEADERS
    print(f"NSE session ready with {len(jar)} cookies.", flush=True)
    return opener


def _run_db_action(action: Any, max_retries: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            started_at = time.perf_counter()
            print(f"Opening DB transaction attempt {attempt}/{max_retries}...", flush=True)
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL statement_timeout = 0"))
                result = action(conn)
            print(
                f"    DB transaction completed in {_format_seconds(time.perf_counter() - started_at)}",
                flush=True,
            )
            return result
        except OperationalError as exc:
            last_error = exc
            if attempt == max_retries:
                break
            wait_seconds = attempt * 2
            print(
                f"  DB connection failed on attempt {attempt}/{max_retries}; retrying in {wait_seconds}s...",
                flush=True,
            )
            time.sleep(wait_seconds)

    assert last_error is not None
    raise last_error


def _fetch_history_window(
    opener: urllib.request.OpenerDirector,
    symbol: str,
    from_date: date,
    to_date: date,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "from": _format_nse_date(from_date),
            "to": _format_nse_date(to_date),
            "symbol": symbol,
            "type": "priceVolumeDeliverable",
            "series": "ALL",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{query}")
    with opener.open(request, timeout=40) as response:
        payload = json.loads(response.read().decode("utf-8"))

    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError(f"Unexpected NSE payload for {symbol}: {payload}")

    return [row for row in data if isinstance(row, dict)]


def _load_nse_listings(symbol: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    sql = (
        "SELECT l.id AS listing_id, l.ticker AS symbol, c.name AS company_name "
        "FROM listings l "
        "JOIN exchanges e ON e.id = l.exchange_id "
        "JOIN companies c ON c.id = l.company_id "
        "WHERE e.code = 'NSE' AND l.ticker IS NOT NULL AND l.ticker <> ''"
    )
    params: dict[str, Any] = {}

    if symbol:
        sql += " AND l.ticker = :symbol"
        params["symbol"] = symbol

    sql += " ORDER BY l.ticker"

    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    print(
        f"Loading NSE listings from DB (symbol={symbol or 'ALL'}, limit={limit if limit is not None else 'none'})...",
        flush=True,
    )

    def action(conn: Any) -> list[dict[str, Any]]:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    return _run_db_action(action)


def _upsert_stock_prices(conn: Any, rows: list[dict[str, Any]], chunk_size: int = 100) -> int:
    if not rows:
        return 0

    sql_prefix = (
        "INSERT INTO stock_prices (listing_id, date, open, high, low, close, volume) VALUES "
    )
    sql_suffix = (
        " ON CONFLICT (listing_id, date) DO UPDATE SET "
        "open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, "
        "close = EXCLUDED.close, volume = EXCLUDED.volume"
    )

    inserted = 0
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        placeholders = []
        params: dict[str, Any] = {}
        for idx, row in enumerate(chunk):
            placeholders.append(
                "(:listing_id_{0}, :date_{0}, :open_{0}, :high_{0}, :low_{0}, :close_{0}, :volume_{0})".format(idx)
            )
            params[f"listing_id_{idx}"] = row["listing_id"]
            params[f"date_{idx}"] = row["date"]
            params[f"open_{idx}"] = row["open"]
            params[f"high_{idx}"] = row["high"]
            params[f"low_{idx}"] = row["low"]
            params[f"close_{idx}"] = row["close"]
            params[f"volume_{idx}"] = row["volume"]

        conn.execute(text(sql_prefix + ", ".join(placeholders) + sql_suffix), params)
        inserted += len(chunk)
        print(
            f"      DB upsert chunk {start + 1}-{start + len(chunk)} / {len(rows)}",
            flush=True,
        )

    return inserted


def _upsert_stock_prices_for_window(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    deduped_rows = {(row["listing_id"], row["date"]): row for row in rows}
    return _run_db_action(lambda conn: _upsert_stock_prices(conn, list(deduped_rows.values())))


def import_nse_price_history(
    years: int = 10,
    symbol: str | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.2,
    lookback_days: int | None = None,
    window_days: int = 365,
) -> dict[str, int]:
    job_started_at = time.perf_counter()
    print("Starting NSE price history import...", flush=True)
    print(
        "Parameters: "
        f"years={years}, "
        f"lookback_days={lookback_days if lookback_days is not None else 'none'}, "
        f"window_days={window_days}, "
        f"symbol={symbol or 'ALL'}, "
        f"limit={limit if limit is not None else 'none'}, "
        f"sleep_seconds={sleep_seconds}",
        flush=True,
    )
    if window_days <= 0:
        raise ValueError("window_days must be greater than 0")

    today = date.today()
    if lookback_days is not None:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be greater than 0")
        start_date = today - timedelta(days=lookback_days - 1)
        windows: list[tuple[date, date]] = []
        cursor = start_date
        while cursor <= today:
            window_end = min(cursor + timedelta(days=window_days - 1), today)
            windows.append((cursor, window_end))
            cursor = window_end + timedelta(days=1)
        print(
            f"Prepared {len(windows)} window(s) from {start_date} to {today} with window_days={window_days}.",
            flush=True,
        )
    else:
        windows = _iter_year_windows(today, years)
        print(f"Prepared {len(windows)} year windows ending on {today}.", flush=True)
    print("Step 1/3: Load NSE listings from DB", flush=True)
    listings = _load_nse_listings(symbol=symbol, limit=limit)
    print("Step 2/3: Bootstrap NSE HTTP session", flush=True)
    opener = _make_nse_opener()
    print("Step 3/3: Fetch and upsert price history", flush=True)

    total_symbols = len(listings)
    total_windows = 0
    total_window_targets = total_symbols * len(windows)
    total_rows_fetched = 0
    total_rows_upserted = 0
    failed_symbols = 0

    print(f"Loaded {total_symbols} NSE listings from DB.", flush=True)
    if lookback_days is not None:
        print(
            f"Fetching {lookback_days} day(s) using {len(windows)} window(s) of up to {window_days} day(s).",
            flush=True,
        )
    else:
        print(f"Fetching {years} years using {len(windows)} one-year windows.", flush=True)
    if windows:
        print(f"Date coverage: {windows[0][0]} -> {windows[-1][1]}", flush=True)
    print(f"Total target windows: {total_window_targets}", flush=True)

    print("Using per-window DB commits for price import.", flush=True)

    for index, listing in enumerate(listings, start=1):
        symbol_started_at = time.perf_counter()
        listing_id = int(listing["listing_id"])
        listing_symbol = str(listing["symbol"])
        company_name = str(listing["company_name"])
        print(f"[{index}/{total_symbols}] {listing_symbol} - {company_name}", flush=True)

        try:
            for window_index, (from_date, to_date) in enumerate(windows, start=1):
                window_started_at = time.perf_counter()
                print(
                    f"  starting window {window_index}/{len(windows)} for {listing_symbol}: {from_date} -> {to_date}",
                    flush=True,
                )
                rows = _fetch_history_window(opener, listing_symbol, from_date, to_date)
                total_windows += 1
                total_rows_fetched += len(rows)
                print(
                    f"  fetched {len(rows)} rows in {_format_seconds(time.perf_counter() - window_started_at)}",
                    flush=True,
                )

                window_rows = [
                    {
                        "listing_id": listing_id,
                        "date": _parse_trade_date(row),
                        "open": _decimal_or_none(row.get("CH_OPENING_PRICE")),
                        "high": _decimal_or_none(row.get("CH_TRADE_HIGH_PRICE")),
                        "low": _decimal_or_none(row.get("CH_TRADE_LOW_PRICE")),
                        "close": _decimal_or_none(row.get("CH_CLOSING_PRICE")),
                        "volume": _int_or_zero(row.get("CH_TOT_TRADED_QTY")),
                    }
                    for row in rows
                ]
                print(
                    f"    normalized {len(window_rows)} rows for DB upsert",
                    flush=True,
                )
                upserted = _upsert_stock_prices_for_window(window_rows)
                total_rows_upserted += upserted
                overall_elapsed = time.perf_counter() - job_started_at
                progress_pct = (total_windows / total_window_targets * 100) if total_window_targets else 100.0
                print(
                    f"    committed {upserted} stock_price rows; cumulative fetched={total_rows_fetched}, upserted={total_rows_upserted}",
                    flush=True,
                )
                print(
                    f"    overall progress: {total_windows}/{total_window_targets} windows ({progress_pct:.2f}%), elapsed={_format_seconds(overall_elapsed)}",
                    flush=True,
                )

                time.sleep(sleep_seconds)
            print(
                f"  completed symbol {listing_symbol} in {_format_seconds(time.perf_counter() - symbol_started_at)}",
                flush=True,
            )
        except Exception as exc:
            failed_symbols += 1
            print(f"  FAILED: {listing_symbol} -> {exc}", flush=True)
            print("  Refreshing NSE session after failure...", flush=True)
            opener = _make_nse_opener()

    total_elapsed = time.perf_counter() - job_started_at
    print(f"Finished NSE import in {_format_seconds(total_elapsed)}", flush=True)

    return {
        "symbols_processed": total_symbols,
        "windows_requested": total_windows,
        "rows_fetched": total_rows_fetched,
        "rows_upserted": total_rows_upserted,
        "failed_symbols": failed_symbols,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import NSE price history into stock_prices.")
    parser.add_argument("--years", type=int, default=10, help="Number of years to backfill.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        help="If set, overrides years and fetches only this many recent days.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=365,
        help="Maximum number of days to request in each NSE API window.",
    )
    parser.add_argument("--symbol", help="Import only one NSE symbol.")
    parser.add_argument("--limit", type=int, help="Limit number of NSE listings for test runs.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Delay between NSE API requests.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    summary = import_nse_price_history(
        years=args.years,
        lookback_days=args.lookback_days,
        window_days=args.window_days,
        symbol=args.symbol,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
    )
    print("Import complete:", summary)
