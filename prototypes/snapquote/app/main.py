"""
SnapQuote v1 - Text to Professional Quote
FastAPI application handling SMS webhooks from ClickSend
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os

from .sms import handle_inbound_sms, send_sms
from .state import ConversationState
from .pdf_gen import generate_quote_pdf

app = FastAPI(title="SnapQuote", version="1.0.0")

# Serve generated quotes
app.mount("/quotes", StaticFiles(directory="quotes"), name="quotes")


class ClickSendInbound(BaseModel):
    """ClickSend inbound SMS webhook payload"""
    from_: str  # sender phone
    to: str     # our TFN
    body: str   # message content
    message_id: Optional[str] = None
    timestamp: Optional[str] = None
    
    class Config:
        # ClickSend uses 'from' which is a Python keyword
        fields = {'from_': 'from'}


@app.get("/")
async def root():
    return {"service": "SnapQuote", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/sms")
async def sms_webhook(request: Request):
    """
    ClickSend inbound SMS webhook
    
    They POST form data or JSON depending on config.
    We handle both.
    """
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)
    
    # Normalize field names (ClickSend uses 'from')
    sender = data.get("from") or data.get("from_")
    body = data.get("body") or data.get("message")
    
    if not sender or not body:
        raise HTTPException(status_code=400, detail="Missing from or body")
    
    # Process the message
    response = await handle_inbound_sms(sender, body.strip())
    
    return {"status": "processed", "response_sent": bool(response)}


@app.get("/quote/{quote_id}")
async def get_quote(quote_id: str):
    """Serve a quote PDF"""
    pdf_path = f"quotes/{quote_id}.pdf"
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Quote not found")
    return FileResponse(pdf_path, media_type="application/pdf")
