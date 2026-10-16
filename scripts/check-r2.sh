#!/usr/bin/env bash
# Usage: AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... scripts/check-r2.sh <endpoint> <bucket> [bucket...]
set -euo pipefail
endpoint="$1"; shift
export AWS_DEFAULT_REGION=auto
key="_ci-probe/$(date +%s)-$$"
fail=0
for bucket in "$@"; do
  if echo ok | aws s3 cp - "s3://$bucket/$key" --endpoint-url "$endpoint" --only-show-errors \
     && aws s3 ls "s3://$bucket/$key" --endpoint-url "$endpoint" >/dev/null \
     && aws s3 rm "s3://$bucket/$key" --endpoint-url "$endpoint" --only-show-errors; then
    echo "OK   $bucket"
  else
    echo "FAIL $bucket"; fail=1
  fi
done
exit $fail
