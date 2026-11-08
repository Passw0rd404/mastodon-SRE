#!/usr/bin/env python3
"""Download a dashboard from grafana.com so it works when provisioned from Git.

Usage: scripts/fetch-dashboard.py <grafana.com id> <output file>

Dashboards from grafana.com ask you to pick a data source on import
(placeholders such as ${DS_PROMETHEUS}). A dashboard provisioned from Git
cannot be asked, so every placeholder is pointed at a data source variable
instead: ds_mimir for Prometheus and ds_loki for Loki. Grafana's built-in
expression engine keeps its fixed name, __expr__.
"""
import json
import sys
import urllib.request

# plugin type -> (what the placeholder becomes, variable to create or None)
MAPPING = {
    "prometheus": ("${ds_mimir}", ("ds_mimir", "Mimir", "prometheus")),
    "loki": ("${ds_loki}", ("ds_loki", "Loki", "loki")),
    "__expr__": ("__expr__", None),
}

if len(sys.argv) != 3:
    sys.exit(__doc__)

dash_id, out = sys.argv[1], sys.argv[2]
url = f"https://grafana.com/api/dashboards/{dash_id}/revisions/latest/download"
request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(request) as response:
    dash = json.load(response)

inputs = [i for i in dash.pop("__inputs", []) if i.get("type") == "datasource"]
dash.pop("__elements", None)

text = json.dumps(dash)
needed_variables = []
replaced = []
for item in inputs:
    target = MAPPING.get(item.get("pluginId"))
    if target is None:
        print(f"warning: no mapping for {item['name']} (plugin {item.get('pluginId')}), left unchanged")
        continue
    reference, variable = target
    text = text.replace("${" + item["name"] + "}", reference)
    replaced.append(f"{item['name']} -> {reference}")
    if variable and variable not in needed_variables:
        needed_variables.append(variable)
dash = json.loads(text)

variables = dash.setdefault("templating", {}).setdefault("list", [])
for name, label, plugin in reversed(needed_variables):
    if not any(v.get("name") == name for v in variables):
        variables.insert(0, {
            "name": name,
            "label": label,
            "type": "datasource",
            "query": plugin,
            "refresh": 1,
            "hide": 0,
        })

dash["id"] = None
dash["uid"] = dash.get("uid") or f"gnet-{dash_id}"

with open(out, "w") as f:
    json.dump(dash, f, indent=2)
    f.write("\n")

print(f"{out}: {dash.get('title')} | uid {dash['uid']} | {replaced or 'no placeholders'}")
