#!/usr/bin/env bash
# Creates a Viewer-role Grafana service account + token, writes ci/grafana-mcp-secret.yaml (gitignored).
set -euo pipefail
: "${GRAFANA_URL:?}" "${GRAFANA_ADMIN_USER:?}" "${GRAFANA_ADMIN_PASSWORD:?}" "${MCP_GRAFANA_SERVER_TOKEN:?}"
NAME="${NAME:-ai-mcp-$(date +%Y%m%d)}"
OUT="${OUT:-charts/ai/ci/grafana-mcp-secret.yaml}"
auth=(-u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" -H 'Content-Type: application/json')

sa_id=$(curl -fsS "${auth[@]}" -X POST "$GRAFANA_URL/api/serviceaccounts" \
  -d "{\"name\":\"$NAME\",\"role\":\"Viewer\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
token=$(curl -fsS "${auth[@]}" -X POST "$GRAFANA_URL/api/serviceaccounts/$sa_id/tokens" \
  -d "{\"name\":\"$NAME\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["key"])')

umask 077
cat > "$OUT" <<YAML
apiVersion: v1
kind: Secret
metadata: {name: grafana-mcp, namespace: ai}
type: Opaque
stringData:
  GRAFANA_SERVICE_ACCOUNT_TOKEN: "$token"
  MCP_GRAFANA_SERVER_TOKEN: "$MCP_GRAFANA_SERVER_TOKEN"
YAML
echo "Wrote $OUT (Viewer service account '$NAME')."
