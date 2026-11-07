#!/usr/bin/env bash
# Gives the CNPG metrics role read access to the few columns the business queries use.
# Run after Mastodon's database migrations have created the tables.
set -euo pipefail
NS="${1:-mastodon}"
PRIMARY=$(kubectl -n "$NS" get pod -l cnpg.io/cluster=mastodon,cnpg.io/instanceRole=primary -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" exec -i "$PRIMARY" -c postgres -- psql -d mastodon -v ON_ERROR_STOP=1 <<'SQL'
GRANT USAGE ON SCHEMA public TO cnpg_metrics_exporter;
GRANT SELECT (id, created_at, confirmed_at, current_sign_in_at, disabled) ON public.users TO cnpg_metrics_exporter;
GRANT SELECT (id, domain) ON public.accounts TO cnpg_metrics_exporter;
GRANT SELECT (id, account_id, created_at) ON public.statuses TO cnpg_metrics_exporter;
GRANT SELECT (id, action_taken_at) ON public.reports TO cnpg_metrics_exporter;
SQL
echo "done"
