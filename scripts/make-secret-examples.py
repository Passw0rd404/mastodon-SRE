#!/usr/bin/env python3
"""Create safe example secrets from the real, git-ignored ci/ secret files.

For every charts/**/ci/*.yaml that contains a Kubernetes Secret, write
<chart dir>/secrets-example/<name>.example.yaml with the same names and keys
but every value replaced by CHANGE_ME. Real values are never copied.
"""
import glob
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is missing. Install it with: sudo pacman -S python-yaml")

PLACEHOLDER = "CHANGE_ME"

for path in sorted(glob.glob("charts/**/ci/*.y*ml", recursive=True)):
    with open(path) as f:
        docs = [d for d in yaml.safe_load_all(f) if isinstance(d, dict) and d.get("kind") == "Secret"]
    if not docs:
        continue
    examples = []
    for doc in docs:
        meta = doc.get("metadata", {})
        keys = list((doc.get("stringData") or {}).keys()) + list((doc.get("data") or {}).keys())
        metadata = {"name": meta.get("name")}
        if meta.get("namespace"):
            metadata["namespace"] = meta["namespace"]
        examples.append({
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": metadata,
            "type": doc.get("type", "Opaque"),
            "stringData": {key: PLACEHOLDER for key in keys},
        })
        print(f"{meta.get('namespace', '?')}/{meta.get('name')}  type={doc.get('type', 'Opaque')}  keys: {', '.join(keys)}")
    target_dir = os.path.join(os.path.dirname(os.path.dirname(path)), "secrets-example")
    os.makedirs(target_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    target = os.path.join(target_dir, f"{base}.example.yaml")
    with open(target, "w") as f:
        f.write("# Example only. Copy it, replace every CHANGE_ME, then: kubectl apply -f <file>\n")
        yaml.safe_dump_all(examples, f, sort_keys=False)
    print(f"   -> {target}")
