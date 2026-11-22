#!/usr/bin/env bash
# Usage: scripts/promq.sh '<promql>'   (prints every series: labels => value)
set -euo pipefail
kubectl -n monitoring port-forward svc/mimir-gateway 18080:80 >/dev/null 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null' EXIT
sleep 3
curl -sG -H "X-Scope-OrgID: sre" "http://localhost:18080/prometheus/api/v1/query" \
  --data-urlencode "query=$1" \
  | jq -r '.data.result[] | ((.metric | to_entries | map("\(.key)=\(.value)") | join(" ")) + "  =>  " + .value[1])' \
  | head -${LIMIT:-40}
