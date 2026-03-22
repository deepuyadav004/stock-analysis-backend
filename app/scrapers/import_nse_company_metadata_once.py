import argparse
import http.cookiejar
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import engine


REPORT_URL = "https://www.nseindia.com/report-detail/eq_security"
QUOTE_API_URL = "https://www.nseindia.com/api/quote-equity"
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
    ("accept", "application/json, text/plain, */*"),
    ("accept-language", "en-US,en;q=0.9"),
    ("priority", "u=1, i"),
    ("sec-ch-ua", '\"Chromium\";v=\"146\", \"Not-A.Brand\";v=\"24\", \"Brave\";v=\"146\"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '\"Windows\"'),
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


def _run_db_action(action: Callable[[Any], Any], max_retries: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL statement_timeout = 0"))
                return action(conn)
        except OperationalError as exc:
            last_error = exc
            if attempt == max_retries:
                break
            wait_seconds = attempt * 2
            print(
                f"DB connection failed on attempt {attempt}/{max_retries}; retrying in {wait_seconds}s...",
                flush=True,
            )
            time.sleep(wait_seconds)

    assert last_error is not None
    raise last_error


def _make_nse_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = PAGE_HEADERS
    print(f"  [NSE] Bootstrapping session via {REPORT_URL} ...", flush=True)
    with opener.open(REPORT_URL, timeout=40):
        pass
    print(f"  [NSE] Session ready ({len(jar)} cookies acquired).", flush=True)
    opener.addheaders = API_HEADERS
    return opener


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        return int(float(cleaned))
    return int(value)


def _extract_company_metadata(payload: dict[str, Any], symbol: str = "") -> dict[str, Any] | None:
    security_info = payload.get("securityInfo")
    industry_info = payload.get("industryInfo")
    if not isinstance(security_info, dict):
        print(f"    [parse] {symbol}: 'securityInfo' key missing or not a dict.", flush=True)
        return None
    if not isinstance(industry_info, dict):
        print(f"    [parse] {symbol}: 'industryInfo' key missing or not a dict.", flush=True)
        return None

    sector_name = _clean_text(industry_info.get("sector"))
    industry_name = _clean_text(industry_info.get("industry"))
    shares_outstanding = _int_or_none(security_info.get("issuedSize"))

    missing = [f for f, v in [("sector", sector_name), ("industry", industry_name), ("issuedSize", shares_outstanding)] if v is None]
    if missing:
        print(f"    [parse] {symbol}: skipping — missing fields: {', '.join(missing)}", flush=True)
        return None

    print(
        f"    [parse] {symbol}: sector='{sector_name}', industry='{industry_name}', "
        f"shares_outstanding={shares_outstanding:,}",
        flush=True,
    )
    return {
        "sector_name": sector_name,
        "industry_name": industry_name,
        "shares_outstanding": shares_outstanding,
    }


def _load_nse_companies(symbol: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    sql = (
        "SELECT c.id AS company_id, c.name AS company_name, l.ticker AS symbol "
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

    return _run_db_action(
        lambda conn: [
            dict(row)
            for row in conn.execute(text(sql), params).mappings().all()
        ]
    )


def _chunked(rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + chunk_size] for i in range(0, len(rows), chunk_size)]


def _multi_insert(
    conn: Any,
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    conflict: str,
    chunk_size: int = 100,
) -> None:
    if not rows:
        return

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        placeholders = ", ".join(
            "(" + ", ".join(f":{col}_{j}" for col in columns) + ")"
            for j, _ in enumerate(chunk)
        )
        params = {
            f"{col}_{j}": row[col]
            for j, row in enumerate(chunk)
            for col in columns
        }
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {placeholders} {conflict}"
        conn.execute(text(sql), params)


def _fetch_quote_payload(
    opener: urllib.request.OpenerDirector,
    symbol: str,
    max_retries: int,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({"symbol": symbol})
    quote_url = f"{QUOTE_API_URL}?{query}"

    for attempt in range(1, max_retries + 1):
        print(
            f"    [fetch] {symbol}: attempt {attempt}/{max_retries} -> {quote_url}",
            flush=True,
        )
        request = urllib.request.Request(
            quote_url,
            headers={
                "referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
            },
        )
        try:
            with opener.open(request, timeout=40) as response:
                raw = response.read().decode("utf-8")
                status = response.status
            print(f"    [fetch] {symbol}: HTTP {status}, {len(raw)} bytes received.", flush=True)
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"Unexpected payload type for {symbol}: {type(payload).__name__}")
            return payload
        except Exception as exc:
            print(f"    [fetch] {symbol}: attempt {attempt} error — {exc}", flush=True)
            if attempt == max_retries:
                raise RuntimeError(f"NSE quote call failed for {symbol}: {exc}") from exc
            wait_seconds = attempt
            print(f"    [fetch] {symbol}: retrying in {wait_seconds}s...", flush=True)
            time.sleep(wait_seconds)

    raise RuntimeError(f"NSE quote call failed for {symbol}")


def _apply_db_updates(rows: list[dict[str, Any]], chunk_size: int = 100) -> dict[str, int]:
    if not rows:
        return {
            "sectors_inserted": 0,
            "industries_inserted": 0,
            "companies_updated": 0,
        }

    def action(conn: Any) -> dict[str, int]:
        sectors = sorted({row["sector_name"] for row in rows})

        print(f"  [db] Processing {len(sectors)} unique sector(s): {sectors}", flush=True)
        existing_sector_ids: dict[str, int] = {}
        new_sector_rows: list[dict[str, Any]] = []
        for sector_name in sectors:
            existing = conn.execute(
                text("SELECT id FROM sectors WHERE name = :name LIMIT 1"),
                {"name": sector_name},
            ).scalar_one_or_none()
            if existing is None:
                print(f"  [db] New sector: '{sector_name}'", flush=True)
                new_sector_rows.append({"name": sector_name})
            else:
                print(f"  [db] Existing sector id={existing}: '{sector_name}'", flush=True)
                existing_sector_ids[sector_name] = int(existing)

        if new_sector_rows:
            print(f"  [db] Inserting {len(new_sector_rows)} new sector(s)...", flush=True)
        _multi_insert(
            conn,
            "sectors",
            ["name"],
            new_sector_rows,
            "ON CONFLICT (name) DO NOTHING",
            chunk_size,
        )

        for sector_name in sectors:
            if sector_name not in existing_sector_ids:
                sector_id = conn.execute(
                    text("SELECT id FROM sectors WHERE name = :name LIMIT 1"),
                    {"name": sector_name},
                ).scalar_one()
                print(f"  [db] Sector inserted with id={sector_id}: '{sector_name}'", flush=True)
                existing_sector_ids[sector_name] = int(sector_id)

        industry_key_to_id: dict[tuple[str, int], int] = {}
        industries_inserted = 0

        unique_industries = sorted(
            {
                (row["industry_name"], existing_sector_ids[row["sector_name"]])
                for row in rows
            }
        )
        print(f"  [db] Processing {len(unique_industries)} unique industry/sector pair(s).", flush=True)

        for industry_name, sector_id in unique_industries:
            existing_industry_id = conn.execute(
                text(
                    "SELECT id FROM industries "
                    "WHERE name = :name AND sector_id = :sector_id "
                    "LIMIT 1"
                ),
                {"name": industry_name, "sector_id": sector_id},
            ).scalar_one_or_none()

            if existing_industry_id is None:
                existing_industry_id = conn.execute(
                    text(
                        "INSERT INTO industries (name, sector_id) "
                        "VALUES (:name, :sector_id) RETURNING id"
                    ),
                    {"name": industry_name, "sector_id": sector_id},
                ).scalar_one()
                industries_inserted += 1
                print(f"  [db] New industry id={existing_industry_id}: '{industry_name}' (sector_id={sector_id})", flush=True)
            else:
                print(f"  [db] Existing industry id={existing_industry_id}: '{industry_name}' (sector_id={sector_id})", flush=True)

            industry_key_to_id[(industry_name, sector_id)] = int(existing_industry_id)

        company_updates = [
            {
                "company_id": row["company_id"],
                "shares_outstanding": row["shares_outstanding"],
                "industry_id": industry_key_to_id[
                    (row["industry_name"], existing_sector_ids[row["sector_name"]])
                ],
            }
            for row in rows
        ]

        print(f"  [db] Updating {len(company_updates)} companies (chunks of {chunk_size})...", flush=True)
        update_sql = text(
            "UPDATE companies "
            "SET shares_outstanding = :shares_outstanding, industry_id = :industry_id "
            "WHERE id = :company_id"
        )
        updated_count = 0
        for chunk in _chunked(company_updates, chunk_size):
            conn.execute(update_sql, chunk)
            updated_count += len(chunk)
            print(f"  [db]   updated {updated_count}/{len(company_updates)} companies.", flush=True)

        return {
            "sectors_inserted": len(new_sector_rows),
            "industries_inserted": industries_inserted,
            "companies_updated": updated_count,
        }

    return _run_db_action(action)


def import_nse_company_metadata_once(
    symbol: str | None = None,
    limit: int | None = None,
    sleep_seconds: float = 0.2,
    dry_run: bool = False,
    max_retries: int = 3,
) -> dict[str, int]:
    started_at = time.perf_counter()
    print("Starting NSE company metadata import...", flush=True)
    print(
        f"Parameters: symbol={symbol or 'ALL'}, limit={limit if limit is not None else 'none'}, "
        f"sleep_seconds={sleep_seconds}, dry_run={dry_run}",
        flush=True,
    )

    listings = _load_nse_companies(symbol=symbol, limit=limit)
    total = len(listings)
    print(f"Loaded {total} NSE companies to process.", flush=True)
    opener = _make_nse_opener()

    rows_to_update: list[dict[str, Any]] = []
    skipped_missing = 0
    failed_requests = 0
    parse_errors = 0

    for idx, row in enumerate(listings, start=1):
        company_id = int(row["company_id"])
        ticker = str(row["symbol"])

        print(f"[{idx}/{total}] Fetching quote for {ticker} (company_id={company_id})...", flush=True)
        try:
            payload = _fetch_quote_payload(opener, ticker, max_retries=max_retries)
        except Exception as exc:
            failed_requests += 1
            print(f"[{idx}/{total}] FAILED {ticker}: {exc}", flush=True)
            print(f"[{idx}/{total}] Refreshing NSE session after failure...", flush=True)
            opener = _make_nse_opener()
            continue

        try:
            metadata = _extract_company_metadata(payload, symbol=ticker)
            if metadata is None:
                skipped_missing += 1
                print(f"[{idx}/{total}] SKIPPED {ticker}: insufficient metadata (see parse log above).", flush=True)
            else:
                rows_to_update.append(
                    {
                        "company_id": company_id,
                        "symbol": ticker,
                        "sector_name": metadata["sector_name"],
                        "industry_name": metadata["industry_name"],
                        "shares_outstanding": metadata["shares_outstanding"],
                    }
                )
                print(f"[{idx}/{total}] OK {ticker}: queued for DB update.", flush=True)
                if idx % 25 == 0 or idx == total:
                    print(
                        f"[{idx}/{total}] --- progress: prepared={len(rows_to_update)}, "
                        f"skipped={skipped_missing}, failed={failed_requests}, parse_errors={parse_errors} ---",
                        flush=True,
                    )
        except Exception as exc:
            parse_errors += 1
            print(f"[{idx}/{total}] PARSE ERROR {ticker}: {exc}", flush=True)

        time.sleep(sleep_seconds)

    db_summary = {
        "sectors_inserted": 0,
        "industries_inserted": 0,
        "companies_updated": 0,
    }
    if not dry_run:
        db_summary = _apply_db_updates(rows_to_update)

    elapsed = time.perf_counter() - started_at
    summary = {
        "symbols_processed": total,
        "symbols_prepared": len(rows_to_update),
        "skipped_missing": skipped_missing,
        "failed_requests": failed_requests,
        "parse_errors": parse_errors,
        "sectors_inserted": db_summary["sectors_inserted"],
        "industries_inserted": db_summary["industries_inserted"],
        "companies_updated": db_summary["companies_updated"],
        "elapsed_seconds": int(elapsed),
    }

    print(f"Completed in {_format_seconds(elapsed)}", flush=True)
    print("Summary:", flush=True)
    for key, value in summary.items():
        print(f"  {key}: {value}", flush=True)

    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-time import of NSE sector/industry/shares_outstanding into DB."
    )
    parser.add_argument("--symbol", help="Run only for one NSE symbol.")
    parser.add_argument("--limit", type=int, help="Limit number of NSE symbols.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Delay between NSE quote API calls.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse data without writing to DB.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retry count for each NSE API request.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_started_at = datetime.now()
    print(f"Run started at: {run_started_at.isoformat(timespec='seconds')}", flush=True)
    import_nse_company_metadata_once(
        symbol=args.symbol,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        dry_run=args.dry_run,
        max_retries=args.max_retries,
    )