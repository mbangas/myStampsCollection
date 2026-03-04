"""Debug script to understand StampData HTML structure."""
import re
import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
resp = requests.get(
    "https://www.stampdata.com/stamps.php?fissuer=39",
    headers=headers,
    timeout=30,
)
print(f"Status: {resp.status_code} | Size: {len(resp.text)}")

# Regex approach on raw HTML
ids = re.findall(r"stamp\.php\?id=(\d+)", resp.text)
unique_ids = list(dict.fromkeys(ids))
print(f"Stamp IDs via regex: {len(unique_ids)} | first 5: {unique_ids[:5]}")

# Check pagination links
offsets = re.findall(r"offset=(\d+)", resp.text)
print(f"Offset values in page: {sorted(set(int(x) for x in offsets))[:10]}")

# Print snippet of raw HTML around first stamp link
match = re.search(r".{0,200}stamp\.php\?id=\d+.{0,200}", resp.text)
if match:
    print("\nHTML snippet around first stamp link:")
    print(match.group(0))

# Check for pagination "Next" link format
soup = BeautifulSoup(resp.text, "lxml")
for a in soup.find_all("a"):
    if a.get_text(strip=True) == "Next":
        print(f"\nNext link: {a.get('href')}")
        break
