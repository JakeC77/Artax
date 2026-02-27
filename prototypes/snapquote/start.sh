#!/bin/bash
cd "$(dirname "$0")"

# Activate venv
source .venv/bin/activate

# Load env
set -a
source .env
set +a

# Inherit ANTHROPIC_API_KEY from environment if not set
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$ANTHROPIC_API_KEY}"

# Create directories
mkdir -p quotes logos

# Start server
echo "Starting SnapQuote on port 8080..."
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
