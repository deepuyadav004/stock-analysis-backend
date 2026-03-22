import http.cookiejar
import json
import urllib.request
import urllib.parse
from typing import Optional

# Mappings from our News tags to official NSE Indices
NEWS_SECTOR_TO_NSE_INDEX = {
    "Automobile and Auto Components": "NIFTY AUTO",
    "Chemicals": "NIFTY CHEMICALS",
    "Consumer Durables": "NIFTY CONSUMER DURABLES",
    "Consumer Services": "NIFTY INDIA CONSUMPTION",
    "Diversified": "NIFTY CONGLOMERATE 50",
    "Fast Moving Consumer Goods": "NIFTY FMCG",
    "Financial Services": "NIFTY FINANCIAL SERVICES",
    "Healthcare": "NIFTY HEALTHCARE INDEX",
    "Information Technology": "NIFTY IT",
    "Media Entertainment & Publication": "NIFTY MEDIA",
    "Metals & Mining": "NIFTY METAL",
    "Oil Gas & Consumable Fuels": "NIFTY OIL & GAS",
    "Power": "NIFTY ENERGY",
    "Realty": "NIFTY REALTY",
    "SERVICES": "NIFTY SERVICES SECTOR",
    "Services": "NIFTY SERVICES SECTOR",
}

def get_nse_opener() -> urllib.request.OpenerDirector:
    """
    Creates a urllib Opener that handles cookies across requests.
    Hits the NSE homepage first to establish the Akamai cookies needed for API access.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    headers = [
        ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
        ("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
        ("accept-language", "en-US,en;q=0.9"),
        ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"'),
        ("sec-ch-ua-platform", '"Windows"'),
    ]
    opener.addheaders = headers
    
    try:
        # Establish session cookies
        opener.open("https://www.nseindia.com/", timeout=15)
    except Exception as e:
        print(f"[NSE Index Scraper] Warning: Failed to initialize NSE session cookies: {e}")
    
    return opener

def fetch_index_advance_decline(index_name: str, opener: urllib.request.OpenerDirector) -> Optional[dict]:
    """
    Hits the NextApi getAdvanceDecline endpoint for a given NIFTY index and returns the raw data dictionary.
    """
    # Overwrite headers for API call (adding referer is critical to bypass 401/403)
    opener.addheaders = [
        ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
        ("accept", "*/*"),
        ("accept-language", "en-US,en;q=0.9"),
        ("referer", f"https://www.nseindia.com/index-tracker/{urllib.parse.quote(index_name)}"),
        ("sec-fetch-dest", "empty"),
        ("sec-fetch-mode", "cors"),
        ("sec-fetch-site", "same-origin"),
    ]
    
    encoded_index = urllib.parse.quote(index_name)
    url = f"https://www.nseindia.com/api/NextApi/apiClient/indexTrackerApi?functionName=getAdvanceDecline&index={encoded_index}"
    
    try:
        resp = opener.open(url, timeout=15)
        raw_data = resp.read().decode("utf-8")
        json_data = json.loads(raw_data)
        
        # The API returns {"data": [{ ... }]}
        if "data" in json_data and isinstance(json_data["data"], list) and len(json_data["data"]) > 0:
            return json_data["data"][0]
        else:
            print(f"[NSE Index Scraper] No 'data' found in response for index {index_name}")
            return None
    except urllib.error.HTTPError as e:
        print(f"[NSE Index Scraper] HTTP Error fetching {index_name}: {e.code} {e.reason}")
    except Exception as e:
        print(f"[NSE Index Scraper] Error fetching {index_name}: {e}")
        
    return None

def fetch_sector_data(news_sector: str, opener: Optional[urllib.request.OpenerDirector] = None) -> Optional[dict]:
    """
    Takes a news sector name, maps it to the NIFTY index, and fetches the advance/decline data.
    """
    nifty_index = NEWS_SECTOR_TO_NSE_INDEX.get(news_sector)
    if not nifty_index:
        # We don't have a mapping for this sector (e.g. 'Construction Materials' might not be perfectly mapped)
        return None
        
    if opener is None:
        opener = get_nse_opener()
        
    return fetch_index_advance_decline(nifty_index, opener)


if __name__ == "__main__":
    # Test execution
    print("Testing NSE Index Scraper mappings...")
    test_sectors = ["Metals & Mining", "Automobile and Auto Components", "Information Technology", "Unknown Sector"]
    
    session_opener = get_nse_opener()
    
    for sector in test_sectors:
        print(f"\nFetching data for news sector: '{sector}'")
        data = fetch_sector_data(sector, session_opener)
        if data:
            print(f"Success! Fetched for index '{data.get('indexName', 'Unknown')}'")
            print(f"Advance: {data.get('advance_symbol')}, Decline: {data.get('decline_symbol')}, Unchanged: {data.get('unchanged_symbol')}")
            print(f"Total Symbols: {data.get('total_symbol')}")
        else:
            print(f"No data returned or unmapped sector.")
