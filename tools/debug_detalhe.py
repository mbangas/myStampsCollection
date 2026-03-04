"""Debug script to check detail page HTML structure."""
import json
import re
import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
resp = requests.get(
    "https://www.stampdata.com/stamp.php?id=105319",
    headers=headers,
    timeout=30,
)
print(f"Status: {resp.status_code} | Size: {len(resp.text)}")

soup = BeautifulSoup(resp.text, "lxml")

# Gather all table rows
rows = {}
for tr in soup.select("table tr"):
    tds = tr.find_all("td")
    if len(tds) >= 2:
        k = tds[0].get_text(strip=True)
        v = tds[1].get_text(strip=True)
        if k:
            rows[k] = v

print(json.dumps(rows, indent=2, ensure_ascii=False))

# Catalog links
cat_links = [a.get_text(strip=True) for a in soup.select('a[href*="catalog.php"]')]
print(f"\nCatalog links: {cat_links}")

# Raw catalog numbers section
cat_section_match = re.search(r"Catalog numbers?:(.*?)(?:\n|External|<)", resp.text)
if cat_section_match:
    print(f"\nCatalog section raw: {cat_section_match.group(1)[:200]}")
