#!/usr/bin/env python3
"""
Polling fallback for ClickSend inbound SMS
Checks for new messages every 5 seconds
"""

import os
import time
import httpx
import asyncio
from datetime import datetime

# Import our handlers
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.sms import handle_inbound_sms

CLICKSEND_USERNAME = os.getenv("CLICKSEND_USERNAME")
CLICKSEND_API_KEY = os.getenv("CLICKSEND_API_KEY")
SNAPQUOTE_NUMBER = os.getenv("SNAPQUOTE_NUMBER", "+18335154305")

# Track processed messages
processed_ids = set()
last_check = int(time.time()) - 300  # Start 5 min ago

async def check_inbound():
    global last_check, processed_ids
    
    auth = (CLICKSEND_USERNAME, CLICKSEND_API_KEY)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://rest.clicksend.com/v3/sms/inbound",
            auth=auth,
            params={"limit": 20}
        )
        
        if response.status_code != 200:
            print(f"Error fetching inbound: {response.status_code}")
            return
        
        data = response.json()
        messages = data.get("data", {}).get("data", [])
        
        for msg in messages:
            msg_id = msg.get("message_id")
            
            # Skip if already processed
            if msg_id in processed_ids:
                continue
                
            # Check if it's for our number
            to_number = msg.get("to")
            if to_number != SNAPQUOTE_NUMBER:
                continue
            
            sender = msg.get("from")
            body = msg.get("body", "").strip()
            
            print(f"[{datetime.now()}] New message from {sender}: {body}")
            
            # Process it
            try:
                response = await handle_inbound_sms(sender, body)
                print(f"  -> Response sent: {bool(response)}")
            except Exception as e:
                print(f"  -> Error: {e}")
            
            processed_ids.add(msg_id)
            
            # Mark as read
            try:
                await client.put(
                    f"https://rest.clicksend.com/v3/sms/inbound-read/{msg_id}",
                    auth=auth
                )
            except:
                pass

async def main():
    print(f"Starting SnapQuote poller for {SNAPQUOTE_NUMBER}")
    print(f"Checking every 5 seconds...")
    
    while True:
        try:
            await check_inbound()
        except Exception as e:
            print(f"Error in poll loop: {e}")
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
