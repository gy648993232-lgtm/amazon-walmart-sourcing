# Check scraped Amazon data
import json
from pathlib import Path

data_files = sorted(Path("data").glob("amazon_*.json"), key=lambda x: -x.stat().st_mtime)
for f in data_files[:2]:
    items = json.load(open(f, encoding="utf-8"))
    print(f"File: {f.name} | Count: {len(items)}")
    for item in items:
        print(f"  {item['name'][:45]:45s} ${item['price_amazon']:6.2f} "
              f"Rt:{item['rating']:3.1f} Rv:{item['reviews_count']:5d}")
    print()
