import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import text

from app.core.database import engine


def _multi_insert(conn, table, columns, rows, conflict, chunk_size=50):
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
        print(f"    {table}: rows {i + 1}-{i + len(chunk)} / {len(rows)}", flush=True)




API_URL = "https://www.5paisa.com/exchangefilter"
API_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.5",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://www.5paisa.com",
    "priority": "u=1, i",
    "referer": "https://www.5paisa.com/stocks/all?exchange=NSE&exchange=BSE&marketcap=SmallCap&marketcap=MidCap&marketcap=LargeCap",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}
API_FORM = {
    "exchange": "NSE,BSE",
    "gain": "",
    "cap": "SmallCap,MidCap,LargeCap",
    "copaction": "",
    "copsplit": "",
    "copbonus": "",
    "coprights": "",
    "sectors": "",
    "stocktech": "",
    "mtf": "",
    "sortField": "4",
    "sortOrder": "High to Low",
    "search": "",
    "ltpMin": "0",
    "ltpMax": "500000",
    "page": "1",
    "limit": "99999",
}


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        for key in ("data", "Data", "result", "Result"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]

    raise ValueError("Unexpected API response format. Expected a list of objects.")


def fetch_exchange_rows() -> list[dict[str, Any]]:
    print("  Calling source API...", flush=True)
    body = urlencode(API_FORM).encode("utf-8")
    request = Request(API_URL, data=body, headers=API_HEADERS, method="POST")

    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    rows = _extract_rows(payload)
    print(f"  API returned {len(rows)} rows.", flush=True)
    return rows


def import_companies_and_listings_once() -> dict[str, int]:
    rows = fetch_exchange_rows()

    inserted_companies = 0
    inserted_listings = 0
    updated_listings = 0
    insert_chunk_size = 50

    with engine.begin() as conn:
        # Disable statement timeout for this bulk import session
        conn.execute(text("SET LOCAL statement_timeout = 0"))
        print("  Statement timeout disabled for import.", flush=True)
        # ── Exchanges ────────────────────────────────────────────────────────
        print("  Upserting exchanges...", flush=True)
        exchange_id_by_code: dict[str, int] = {}
        for code in ("NSE", "BSE"):
            existing = conn.execute(
                text("SELECT id FROM exchanges WHERE code = :code LIMIT 1"),
                {"code": code},
            ).scalar_one_or_none()
            if existing is None:
                existing = conn.execute(
                    text("INSERT INTO exchanges (code) VALUES (:code) RETURNING id"),
                    {"code": code},
                ).scalar_one()
            exchange_id_by_code[code] = int(existing)

        # ── Bulk-load existing companies into memory ──────────────────────
        print("  Loading existing companies from DB...", flush=True)
        existing_companies: dict[str, int] = {}
        for r in conn.execute(text("SELECT id, name FROM companies")).mappings():
            existing_companies[r["name"]] = r["id"]

        # ── Bulk-load existing listings into memory ───────────────────────
        print("  Loading existing listings from DB...", flush=True)
        # key: (company_id, exchange_id) -> {id, ticker}
        existing_listings: dict[tuple[int, int], dict] = {}
        for r in conn.execute(
            text("SELECT id, company_id, exchange_id, ticker FROM listings")
        ).mappings():
            existing_listings[(r["company_id"], r["exchange_id"])] = {
                "id": r["id"],
                "ticker": r["ticker"],
            }

        # ── Process rows ─────────────────────────────────────────────────
        print(f"  Processing {len(rows)} source rows...", flush=True)
        new_company_names: set[str] = set()
        new_listings: list[dict] = []
        update_listings: list[dict] = []

        for row in rows:
            company_name = (row.get("comp_name") or "").strip()
            exchange_code = (row.get("exchange") or "").strip().upper()
            ticker = row.get("symbol")
            if isinstance(ticker, str):
                ticker = ticker.strip() or None

            if not company_name or exchange_code not in exchange_id_by_code:
                continue

            if company_name not in existing_companies:
                new_company_names.add(company_name)

        # ── Batch insert new companies ────────────────────────────────────
        if new_company_names:
            sorted_company_names = sorted(new_company_names)
            print(
                f"  Inserting {len(sorted_company_names)} unique new companies in chunks...",
                flush=True,
            )
            company_rows = [{"name": n, "sector": None} for n in sorted_company_names]
            _multi_insert(conn, "companies", ["name", "sector"], company_rows,
                          "ON CONFLICT (name) DO NOTHING", insert_chunk_size)
            inserted_companies = len(sorted_company_names)
            # Reload full map after bulk insert
            existing_companies = {
                r["name"]: r["id"]
                for r in conn.execute(text("SELECT id, name FROM companies")).mappings()
            }

        # ── Classify listings ─────────────────────────────────────────────
        for row in rows:
            company_name = (row.get("comp_name") or "").strip()
            exchange_code = (row.get("exchange") or "").strip().upper()
            ticker = row.get("symbol")
            if isinstance(ticker, str):
                ticker = ticker.strip() or None

            if not company_name or exchange_code not in exchange_id_by_code:
                continue

            company_id = existing_companies.get(company_name)
            if company_id is None:
                continue

            exchange_id = exchange_id_by_code[exchange_code]
            key = (company_id, exchange_id)
            existing = existing_listings.get(key)

            if existing is None:
                new_listings.append(
                    {"company_id": company_id, "exchange_id": exchange_id, "ticker": ticker}
                )
                existing_listings[key] = {"id": -1, "ticker": ticker}
            elif existing["ticker"] != ticker:
                update_listings.append({"id": existing["id"], "ticker": ticker})
                existing_listings[key]["ticker"] = ticker

        # ── Batch insert new listings ─────────────────────────────────────
        if new_listings:
            print(f"  Inserting {len(new_listings)} new listings in chunks...", flush=True)
            _multi_insert(conn, "listings", ["company_id", "exchange_id", "ticker"],
                          new_listings, "ON CONFLICT (company_id, exchange_id) DO NOTHING",
                          insert_chunk_size)
            inserted_listings = len(new_listings)

        # ── Batch update changed tickers ──────────────────────────────────
        if update_listings:
            print(f"  Updating {len(update_listings)} changed tickers in chunks...", flush=True)
            _multi_insert(conn, "listings", ["ticker", "id"],
                          [{"ticker": r["ticker"], "id": r["id"]} for r in update_listings],
                          "ON CONFLICT (id) DO UPDATE SET ticker = EXCLUDED.ticker",
                          insert_chunk_size)
            updated_listings = len(update_listings)

    return {
        "rows_fetched": len(rows),
        "companies_inserted": inserted_companies,
        "listings_inserted": inserted_listings,
        "listings_updated": updated_listings,
    }


if __name__ == "__main__":
    summary = import_companies_and_listings_once()
    print("Import complete:", summary)
