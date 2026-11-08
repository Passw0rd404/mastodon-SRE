#!/usr/bin/env python3
"""Check dashboards for data source problems before you commit them.

Usage: scripts/check-dashboards.py [files...]   (default: dashboards/*/*.json)

Reports, for each file:
  - variables used as a data source but never defined
    (this is what causes the "ds_loki not found" error)
  - data sources that are hard-coded instead of coming from a variable
"""
import glob
import json
import re
import sys

BUILT_IN = {"", "-- Grafana --", "-- Mixed --", "-- Dashboard --", "grafana", "__expr__"}


def datasource_refs(node):
    """Yield every value used as a data source anywhere in the dashboard."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "datasource":
                if isinstance(value, dict):
                    yield value.get("uid") or ""
                elif isinstance(value, str):
                    yield value
            else:
                yield from datasource_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from datasource_refs(item)


problems = 0
files = sys.argv[1:] or sorted(glob.glob("dashboards/*/*.json"))
for path in files:
    with open(path) as f:
        dash = json.load(f)
    defined = {v.get("name") for v in dash.get("templating", {}).get("list", [])}
    missing, hardcoded = set(), set()
    for ref in set(datasource_refs(dash)):
        match = re.match(r"\$\{?(\w+)", ref)
        if match:
            if match.group(1) not in defined:
                missing.add(ref)
        elif ref not in BUILT_IN:
            hardcoded.add(ref)
    if missing or hardcoded:
        problems += 1
        print(f"CHECK {path}")
        for ref in sorted(missing):
            print(f"   variable not defined: {ref}")
        for ref in sorted(hardcoded):
            print(f"   hard-coded data source: {ref}")
    else:
        print(f"OK    {path}")

sys.exit(1 if problems else 0)
