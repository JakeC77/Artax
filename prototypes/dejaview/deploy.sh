#!/bin/bash
# Deploy DejaView API to the droplet
# Run this ON the droplet as openclaw user
set -e
echo "Deploying DejaView..."
cd /home/openclaw
mkdir -p dejaview && cd dejaview
if [ -d "Artax" ]; then cd Artax && git pull && cd ..; else git clone https://github.com/JakeC77/Artax.git; fi
cp Artax/prototypes/dejaview/api.py .
cp Artax/prototypes/dejaview/requirements.txt .
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Code deployed. Create .env and systemd service next."
