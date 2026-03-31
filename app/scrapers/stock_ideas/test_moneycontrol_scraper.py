from datetime import date
from decimal import Decimal

from app.scrapers.stock_ideas.moneycontrol_scraper import MoneycontrolStockIdeasScraper


def test_parse_recommendations_extracts_common_fields() -> None:
    html = """
    <html>
      <body>
        <table>
          <tbody>
            <tr>
              <td class="company_name">Infosys (INFY)</td>
              <td class="recommendation">Buy</td>
              <td class="target_price">Rs 2500</td>
              <td class="date">2026-03-31</td>
              <td class="rationale">Strong earnings growth visibility</td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """

    scraper = MoneycontrolStockIdeasScraper()
    rows = scraper.parse_recommendations(html)

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "INFY"
    assert row["company_name"] == "Infosys"
    assert row["call_type"] == "BUY"
    assert row["target_price"] == Decimal("2500")
    assert row["recommendation_date"] == date(2026, 3, 31)
    assert row["source"] == "moneycontrol"
    assert row["brief_rationale"] == "Strong earnings growth visibility"
