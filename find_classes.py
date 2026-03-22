from bs4 import BeautifulSoup
import sys

def main():
    try:
        with open("livemint_article.html", "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        
        p_tags = soup.find_all("p")
        parents = {}
        for p in p_tags:
            parent = p.parent
            classes = tuple(parent.get("class", []))
            parents[classes] = parents.get(classes, 0) + 1
            
        for c, count in parents.items():
            print(c, count)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
