#!/usr/bin/env python3
"""Point hard-coded Prometheus data sources at the ds_mimir dropdown.

Usage: scripts/fix-datasources.py <dashboard.json> [more files...]
"""
import json
import sys


def fix(node):
    changed = 0
    if isinstance(node, dict):
        ds = node.get("datasource")
        if isinstance(ds, dict) and ds.get("type") == "prometheus" and not str(ds.get("uid", "")).startswith("$"):
            ds["uid"] = "${ds_mimir}"
            changed += 1
        elif isinstance(ds, str) and ds.lower() == "prometheus":
            node["datasource"] = "${ds_mimir}"
            changed += 1
        for value in node.values():
            changed += fix(value)
    elif isinstance(node, list):
        for item in node:
            changed += fix(item)
    return changed


for path in sys.argv[1:] or sys.exit(__doc__):
    with open(path) as f:
        dash = json.load(f)
    changed = fix(dash)
    variables = dash.setdefault("templating", {}).setdefault("list", [])
    if changed and not any(v.get("name") == "ds_mimir" for v in variables):
        variables.insert(0, {"name": "ds_mimir", "label": "Mimir", "type": "datasource",
                             "query": "prometheus", "refresh": 1, "hide": 0})
    with open(path, "w") as f:
        json.dump(dash, f, indent=2)
        f.write("\n")
    print(f"{path}: {changed} references fixed")
