#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
set -a; source .env; set +a
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$ANTHROPIC_API_KEY}"
mkdir -p quotes logos
echo "Starting SnapQuote on port 8080..."
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
