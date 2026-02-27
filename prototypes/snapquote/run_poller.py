#!/usr/bin/env python3
"""
SnapQuote SMS Poller - No URLs (ClickSend content filter workaround)
"""

import os
import sys
import time
import httpx
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CLICKSEND_USERNAME = os.environ.get("CLICKSEND_USERNAME")
CLICKSEND_API_KEY = os.environ.get("CLICKSEND_API_KEY")
SNAPQUOTE_NUMBER = os.environ.get("SNAPQUOTE_NUMBER", "+18335154305")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")

print(f"SnapQuote Poller Starting", flush=True)
print(f"  Number: {SNAPQUOTE_NUMBER}", flush=True)
print(f"  Base URL: {BASE_URL}", flush=True)
print(flush=True)

processed = set()
last_timestamp = int(time.time()) - 60

def check_messages():
    global last_timestamp
    
    try:
        r = httpx.get(
            "https://rest.clicksend.com/v3/sms/history",
            auth=(CLICKSEND_USERNAME, CLICKSEND_API_KEY),
            params={"limit": 10, "direction": "in"},
            timeout=10
        )
        
        if r.status_code != 200:
            return
            
        data = r.json()
        messages = data.get("data", {}).get("data", [])
        
        for msg in reversed(messages):
            msg_id = msg.get("message_id")
            msg_time = msg.get("date", 0)
            
            if msg_time <= last_timestamp or msg_id in processed:
                continue
            
            to_num = msg.get("to", "")
            if to_num != SNAPQUOTE_NUMBER:
                processed.add(msg_id)
                continue
            
            sender = msg.get("from", "")
            body = msg.get("body", "").strip()
            
            print(f"\n[{datetime.now()}] NEW: {sender} -> {body}", flush=True)
            
            try:
                process_message(sender, body)
            except Exception as e:
                print(f"  ERROR: {e}", flush=True)
            
            processed.add(msg_id)
            last_timestamp = max(last_timestamp, msg_time)
                
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)

def process_message(sender, body):
    from app.state import state
    from app.parser import parse_with_regex
    from app.pdf_gen import generate_quote_pdf
    
    parsed = parse_with_regex(body, None)
    
    print(f"  -> customer={parsed.customer_name}, items={len(parsed.items)}", flush=True)
    
    if not parsed.items:
        send_reply(sender, "Need prices! Try: John Smith - deck repair 450, railing 275")
        return
    
    if not parsed.customer_name:
        convo = state.get(sender)
        convo.quote.items = parsed.items
        state.update(sender, convo)
        
        items_str = ", ".join(f"{i['description']} ${i['amount']:.0f}" for i in parsed.items[:3])
        send_reply(sender, f"Got: {items_str}. Customer name?")
        return
    
    parsed.calculate_total()
    
    quote_id = generate_quote_pdf(
        customer_name=parsed.customer_name,
        items=parsed.items,
        total=parsed.total,
        notes=parsed.notes
    )
    
    # No URL - just code. User can visit snapquote.app/CODE
    reply = f"Quote ready for {parsed.customer_name}! Total: ${parsed.total:.0f}. Code: {quote_id}"
    send_reply(sender, reply)
    print(f"  -> Quote {quote_id} (${parsed.total:.0f})", flush=True)

def send_reply(to, message):
    print(f"  <- {message}", flush=True)
    
    r = httpx.post(
        "https://rest.clicksend.com/v3/sms/send",
        auth=(CLICKSEND_USERNAME, CLICKSEND_API_KEY),
        json={"messages": [{"from": SNAPQUOTE_NUMBER, "to": to, "body": message}]},
        timeout=10
    )
    
    status = r.json().get("data", {}).get("messages", [{}])[0].get("status", "?")
    print(f"  [SMS: {status}]", flush=True)

while True:
    check_messages()
    time.sleep(3)
