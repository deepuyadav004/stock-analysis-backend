import http.cookiejar
import json
import urllib.request

PAGE_HEADERS = [
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
    ("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
    ("accept-language", "en-US,en;q=0.9"),
    ("referer", "https://www.nseindia.com/report-detail/eq_security"),
]
API_HEADERS = [
    ("accept", "*/*"),
    ("accept-language", "en-US,en;q=0.9"),
    ("priority", "u=1, i"),
    ("referer", "https://www.nseindia.com/report-detail/eq_security"),
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("sec-fetch-dest", "empty"),
    ("sec-fetch-mode", "cors"),
    ("sec-fetch-site", "same-origin"),
    ("sec-gpc", "1"),
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
]

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = PAGE_HEADERS
page = opener.open("https://www.nseindia.com/report-detail/eq_security", timeout=40)
print("page", page.status, "cookies", len(jar))
opener.addheaders = API_HEADERS
url = "https://www.nseindia.com/api/historicalOR/generateSecurityWiseHistoricalData?from=14-03-2025&to=14-03-2026&symbol=SWIGGY&type=priceVolumeDeliverable&series=ALL"
resp = opener.open(url, timeout=40)
raw = resp.read().decode("utf-8")
print("api", resp.status, len(raw))
payload = json.loads(raw)
print(list(payload.keys()))
print(payload["data"][0])
