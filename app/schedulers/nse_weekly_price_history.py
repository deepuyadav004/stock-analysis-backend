from datetime import date

from app.scrapers.import_nse_price_history import import_nse_price_history


def run_nse_weekly_price_history() -> dict[str, int]:
    """Run weekly NSE price import for last 7 days in one API window."""
    print(
        f"\n--- Starting Weekly NSE Price Import for {date.today()} ---",
        flush=True,
    )
    summary = import_nse_price_history(
        lookback_days=7,
        window_days=7,
        sleep_seconds=0.2,
    )
    print("--- Weekly NSE Price Import Complete ---", flush=True)
    return summary