#!/usr/bin/env bash
# One raw curl. Verifies the endpoint + auth + body shape with no Python in the way.
set -u
[ -f .env ] && set -a && . ./.env && set +a
: "${OPENROUTER_API_KEY:?put OPENROUTER_API_KEY in .env}"

curl -sS -o /tmp/jev_smoke.json -w 'http %{http_code} in %{time_total}s\n' \
  https://openrouter.ai/api/alpha/decisions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "~typesafe/jev-latest",
    "state": "Help! My payouts have been failing for 3 days.",
    "questions": {
      "is_urgent": { "type": "noul", "instructions": "Does this message convey urgency?" }
    }
  }'
{ command -v jq >/dev/null && jq . /tmp/jev_smoke.json || cat /tmp/jev_smoke.json; }
