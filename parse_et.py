from bs4 import BeautifulSoup

with open("et_main.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

for a in soup.find_all("a"):
    text = a.get_text(strip=True).lower()
    if "load" in text or "more" in text or "next" in text:
        print(text, "=>", a.get("href"))

print("Looking for load more divs...")
for div in soup.find_all(["div", "span", "button"]):
    text = div.get_text(strip=True).lower()
    if text == "load more" or text == "show more":
        print("Found load more element:", div.name, div.attrs)
