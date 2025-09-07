#!/usr/bin/env bash
set -euo pipefail
export AGENT_BACKEND=${AGENT_BACKEND:-none}
export MOCK=${MOCK:-true}
if [ -f .env ]; then set -o allexport; source .env; set +o allexport; fi
python -m uvicorn app.main:app --reload
