#!/bin/bash
# Full DejaView droplet setup - run as openclaw on 64.23.173.57
set -e

echo "=== 1. Cloning/updating code ==="
cd /home/openclaw
if [ -d "dejaview" ]; then
  cd dejaview && git pull && cd ..
else
  git clone https://github.com/JakeC77/Artax.git dejaview
fi

echo "=== 2. Installing dependencies ==="
cd /home/openclaw/dejaview/prototypes/dejaview
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt fastapi uvicorn neo4j pydantic python-dotenv --quiet

echo "=== 3. Creating .env (if not exists) ==="
if [ ! -f /home/openclaw/dejaview/.env ]; then
cat > /home/openclaw/dejaview/.env << ENV
NEO4J_URI=neo4j+s://55a20be7.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=REPLACE_WITH_NEO4J_PASSWORD
DEJAVIEW_API_KEY=dv_$(openssl rand -hex 24)
ENV
echo ">>> EDIT /home/openclaw/dejaview/.env with your Neo4j password!"
fi

echo "=== 4. Installing systemd service ==="
sudo tee /etc/systemd/system/dejaview.service > /dev/null << SVC
[Unit]
Description=DejaView API
After=network.target

[Service]
Type=simple
User=openclaw
WorkingDirectory=/home/openclaw/dejaview/prototypes/dejaview
EnvironmentFile=/home/openclaw/dejaview/.env
ExecStart=/home/openclaw/dejaview/prototypes/dejaview/venv/bin/uvicorn api:app --host 127.0.0.1 --port 8100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

sudo systemctl daemon-reload
sudo systemctl enable dejaview
sudo systemctl restart dejaview
sleep 2
sudo systemctl status dejaview --no-pager

echo "=== 5. Caddy config ==="
echo "Add this to your Caddyfile:"
echo ""
echo "api.dejaview.io {"
echo "    reverse_proxy localhost:8100"
echo "}"
echo ""
echo "app.dejaview.io {"
echo "    reverse_proxy localhost:8100"
echo "    redir / /docs"
echo "}"
echo ""
echo "Then: sudo systemctl reload caddy"
echo ""
echo "=== Done! Test with: curl https://api.dejaview.io/v1/health ==="
