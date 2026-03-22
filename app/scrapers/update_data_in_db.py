from datetime import datetime

from app.scrapers.import_companies_once import import_companies_and_listings_once


def run_update() -> dict[str, int]:
    """Update database with latest company/listing snapshot from source API."""
    return import_companies_and_listings_once()


if __name__ == "__main__":
    started_at = datetime.now()
    print("Starting database update...", flush=True)

    result = run_update()
    elapsed_seconds = (datetime.now() - started_at).total_seconds()

    print("Database update completed:")
    print(f"  rows_fetched: {result['rows_fetched']}")
    print(f"  companies_inserted: {result['companies_inserted']}")
    print(f"  listings_inserted: {result['listings_inserted']}")
    print(f"  listings_updated: {result['listings_updated']}")
    print(f"  elapsed_seconds: {elapsed_seconds:.1f}")
