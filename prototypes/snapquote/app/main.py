"""
SnapQuote v1 - Text to Professional Quote
FastAPI application handling SMS webhooks from ClickSend
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import os
import json

from .sms import handle_inbound_sms, send_sms
from .state import ConversationState
from .pdf_gen import generate_quote_pdf

app = FastAPI(title="SnapQuote", version="1.0.0")

# Get the base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Serve generated quotes
app.mount("/quotes", StaticFiles(directory=os.path.join(BASE_DIR, "quotes")), name="quotes")

# Serve static files (hero.png, etc)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the marketing page"""
    index_path = os.path.join(BASE_DIR, "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return {"service": "SnapQuote", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api")
async def api_status():
    return {"service": "SnapQuote", "status": "running"}


@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """
    ClickSend inbound SMS webhook
    """
    content_type = request.headers.get("content-type", "")
    
    # Log everything for debugging
    print(f"=== WEBHOOK HIT ===", flush=True)
    print(f"Content-Type: {content_type}", flush=True)
    
    body_bytes = await request.body()
    print(f"Raw body: {body_bytes}", flush=True)
    
    if "application/json" in content_type:
        data = json.loads(body_bytes)
    elif "form" in content_type or "urlencoded" in content_type:
        form = await request.form()
        data = dict(form)
    else:
        # Try JSON first, then form
        try:
            data = json.loads(body_bytes)
        except:
            data = dict(await request.form())
    
    print(f"Parsed data: {data}", flush=True)
    
    # ClickSend field names (they use various formats)
    sender = data.get("from") or data.get("from_") or data.get("from_number") or data.get("sender_id")
    body = data.get("body") or data.get("message") or data.get("message_body") or data.get("sms_message_body")
    
    print(f"Extracted - sender: {sender}, body: {body}", flush=True)
    
    if not sender or not body:
        print(f"Missing fields! Keys available: {list(data.keys())}", flush=True)
        return {"status": "missing_fields", "keys": list(data.keys())}
    
    # Process the message
    response = await handle_inbound_sms(sender, body.strip())
    
    return {"status": "processed", "response_sent": bool(response)}


@app.get("/quote/{quote_id}")
async def get_quote(quote_id: str):
    """Serve a quote PDF"""
    pdf_path = os.path.join(BASE_DIR, "quotes", f"{quote_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Quote not found")
    return FileResponse(pdf_path, media_type="application/pdf")


# Serve hero.png at root level for the HTML
@app.get("/hero.png")
async def hero_image():
    hero_path = os.path.join(BASE_DIR, "static", "hero.png")
    if os.path.exists(hero_path):
        return FileResponse(hero_path)
    raise HTTPException(status_code=404, detail="Image not found")
