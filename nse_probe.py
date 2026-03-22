import http.cookiejar
import json
import urllib.request

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
    ("accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"),
    ("accept-language", "en-US,en;q=0.9"),
    ("cache-control", "no-cache"),
    ("pragma", "no-cache"),
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("sec-fetch-dest", "document"),
    ("sec-fetch-mode", "navigate"),
    ("sec-fetch-site", "none"),
    ("sec-fetch-user", "?1"),
    ("upgrade-insecure-requests", "1"),
]

page = opener.open("https://www.nseindia.com/report-detail/eq_security", timeout=40)
print("page", page.status, "cookies", len(jar))

opener.addheaders = [
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
    ("accept", "application/json, text/plain, */*"),
    ("accept-language", "en-US,en;q=0.9"),
    ("referer", "https://www.nseindia.com/report-detail/eq_security"),
    ("cache-control", "no-cache"),
    ("pragma", "no-cache"),
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("sec-fetch-dest", "empty"),
    ("sec-fetch-mode", "cors"),
    ("sec-fetch-site", "same-origin"),
]

url = "https://www.nseindia.com/api/historical/cm/equity?symbol=RELIANCE&series=[%22EQ%22]&from=14-03-2016&to=14-03-2026"
resp = opener.open(url, timeout=40)
print("api", resp.status)
payload = json.loads(resp.read().decode("utf-8"))
print(type(payload).__name__)
if isinstance(payload, dict):
    print(list(payload.keys())[:20])
    for key in ("data", "grapthData", "graphData"):
        value = payload.get(key)
        if isinstance(value, list):
            print(key, len(value))
            if value:
                print(value[0])
                break
else:
    print(len(payload))
