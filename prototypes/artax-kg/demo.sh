#!/bin/bash
API="http://localhost:8000"
echo "Artax Knowledge Graph Demo"
curl -s "$API/agent/context" | python3 -m json.tool
