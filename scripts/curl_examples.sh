#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://127.0.0.1:8000}
curl -s $BASE/health
curl -s -X POST $BASE/generate/market-context -H 'Content-Type: application/json' -d @samples/sample_request_spx.json
