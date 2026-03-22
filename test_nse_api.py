import http.cookiejar
import json
import urllib.request
import urllib.parse

def test_fetch():
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
    
    # 1. Probe main page for Akamai cookies
    print("Fetching homepage for cookies...")
    try:
        page = opener.open("https://www.nseindia.com/", timeout=15)
        print("Homepage status:", page.status, "Cookies:", len(jar))
    except Exception as e:
        print("Failed to get homepage:", e)
        return
        
    # 2. Add API specific headers
    opener.addheaders = headers + [
        ("referer", "https://www.nseindia.com/"),
        ("accept", "*/*"),
        ("sec-fetch-dest", "empty"),
        ("sec-fetch-mode", "cors"),
        ("sec-fetch-site", "same-origin")
    ]
    
    # Let's try the user's API
    index_name = urllib.parse.quote("NIFTY METAL")
    url1 = f"https://www.nseindia.com/api/NextApi/apiClient/indexTrackerApi?functionName=getAdvanceDecline&index={index_name}"
    
    print(f"\nFetching {url1}...")
    try:
        resp = opener.open(url1, timeout=15)
        print("API 1 Status:", resp.status)
        data = json.loads(resp.read().decode("utf-8"))
        print(json.dumps(data, indent=2)[:300]) # Print snippet
    except Exception as e:
        print("API 1 Error:", e)

    # Let's try allIndices API which has price data
    url2 = "https://www.nseindia.com/api/allIndices"
    print(f"\nFetching {url2}...")
    try:
        resp = opener.open(url2, timeout=15)
        print("API 2 Status:", resp.status)
        data = json.loads(resp.read().decode("utf-8"))
        # find NIFTY METAL
        metal = next((item for item in data.get("data", []) if item["index"] == "NIFTY METAL"), None)
        print("NIFTY METAL from allIndices:")
        print(json.dumps(metal, indent=2))
    except Exception as e:
        print("API 2 Error:", e)

if __name__ == "__main__":
    test_fetch()
