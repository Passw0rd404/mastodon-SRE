#!/usr/bin/env python3
"""Download the compiled dashboards of a Grafana mixin from GitHub.

Usage: scripts/fetch-mixin.py <owner/repo> <directory in repo> <output dir> [name-regex]
"""
import json
import os
import re
import sys
import urllib.request

if len(sys.argv) not in (4, 5):
    sys.exit(__doc__)

repo, directory, out_dir = sys.argv[1:4]
pattern = re.compile(sys.argv[4]) if len(sys.argv) == 5 else None


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request) as response:
        return response.read()


listing = json.loads(get(f"https://api.github.com/repos/{repo}/contents/{directory}"))
os.makedirs(out_dir, exist_ok=True)
count = 0
for item in listing:
    name = item["name"]
    if not name.endswith(".json") or (pattern and not pattern.search(name)):
        continue
    dash = json.loads(get(item["download_url"]))
    dash["id"] = None
    with open(os.path.join(out_dir, name), "w") as f:
        json.dump(dash, f, indent=2)
        f.write("\n")
    print(f"{out_dir}/{name}: {dash.get('title')}")
    count += 1
print(f"{count} dashboards saved")
