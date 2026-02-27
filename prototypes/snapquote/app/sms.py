"""
SMS handling for SnapQuote
Inbound processing + outbound via ClickSend
"""

import os
import httpx
import json
from typing import Optional, Dict, List

from .state import state, ConvoStage, QuoteData
from .parser import parse_estimate
from .pdf_gen import generate_quote_pdf
from .logos import get_logo_path, save_logo


# ClickSend config
CLICKSEND_USERNAME = os.getenv("CLICKSEND_USERNAME")
CLICKSEND_API_KEY = os.getenv("CLICKSEND_API_KEY")
SNAPQUOTE_NUMBER = os.getenv("SNAPQUOTE_NUMBER", "+18335154305")
BASE_URL = os.getenv("BASE_URL", "https://snapquote.example.com")


async def send_sms(to: str, message: str) -> bool:
    """Send SMS via ClickSend"""
    if not CLICKSEND_USERNAME or not CLICKSEND_API_KEY:
        print(f"[DEV MODE] Would send to {to}: {message}")
        return True
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://rest.clicksend.com/v3/sms/send",
            auth=(CLICKSEND_USERNAME, CLICKSEND_API_KEY),
            json={
                "messages": [{
                    "from": SNAPQUOTE_NUMBER,
                    "to": to,
                    "body": message
                }]
            }
        )
        return response.status_code == 200


async def handle_inbound_sms(sender: str, body: str) -> Optional[str]:
    """
    Main inbound SMS handler
    Routes through conversation state machine
    """
    convo = state.get(sender)
    convo.raw_messages.append(body)
    
    # Check for logo upload (MMS with image)
    if is_logo_upload(body):
        return await handle_logo_upload(sender, body)
    
    # Check for special commands
    lower_body = body.lower().strip()
    if lower_body in ["reset", "start over", "cancel"]:
        state.clear(sender)
        response = "Got it, starting fresh. Text me your estimate anytime!"
        await send_sms(sender, response)
        return response
    
    if lower_body in ["help", "?"]:
        response = ("SnapQuote turns your texts into pro PDF quotes!\n\n"
                   "Just text your estimate like:\n"
                   "\"John Smith - deck repair $450, railing $275\"\n\n"
                   "I'll send back a link to a professional quote PDF.")
        await send_sms(sender, response)
        return response
    
    # Parse the message for quote info
    parsed = await parse_estimate(body, convo.quote)
    
    # Merge parsed data into conversation
    if parsed.customer_name:
        convo.quote.customer_name = parsed.customer_name
    if parsed.items:
        # Replace or extend items based on context
        if convo.stage == ConvoStage.NEED_ITEMS:
            convo.quote.items = parsed.items
        else:
            convo.quote.items.extend(parsed.items)
    if parsed.notes:
        convo.quote.notes = parsed.notes
    
    # Determine next action
    response = await determine_response(sender, convo)
    state.update(sender, convo)
    
    return response


async def determine_response(sender: str, convo) -> str:
    """Decide what to say based on conversation state"""
    quote = convo.quote
    
    # Check what's missing
    missing_customer = not quote.customer_name
    missing_items = not quote.items or len(quote.items) == 0
    
    # If we have everything, generate the quote
    if quote.is_complete():
        return await generate_and_send_quote(sender, convo)
    
    # Ask for missing info (prioritize items over customer name)
    if missing_items:
        convo.stage = ConvoStage.NEED_ITEMS
        if quote.customer_name:
            response = f"Got it for {quote.customer_name}. What are the line items and prices?"
        else:
            response = "What would you like to quote? Include items and prices, like: deck repair $450, railing $275"
        await send_sms(sender, response)
        return response
    
    if missing_customer:
        convo.stage = ConvoStage.NEED_CUSTOMER
        # Summarize what we have
        items_summary = ", ".join(f"{i['description']} ${i['amount']}" for i in quote.items[:3])
        response = f"Got: {items_summary}. Customer name for the quote?"
        await send_sms(sender, response)
        return response
    
    # Shouldn't get here, but fallback
    response = "Something went wrong. Text 'reset' to start over."
    await send_sms(sender, response)
    return response


async def generate_and_send_quote(sender: str, convo) -> str:
    """Generate PDF and send link"""
    quote = convo.quote
    quote.calculate_total()
    
    # Get contractor's logo if they have one
    logo_path = get_logo_path(sender)
    
    # Generate PDF
    quote_id = generate_quote_pdf(
        customer_name=quote.customer_name,
        items=quote.items,
        total=quote.total,
        notes=quote.notes,
        logo_path=logo_path
    )
    
    quote_url = f"{BASE_URL}/quote/{quote_id}"
    
    response = f"Your quote is ready!\n\n{quote_url}\n\nShare this link with {quote.customer_name}."
    await send_sms(sender, response)
    
    # Clear conversation for next quote
    convo.stage = ConvoStage.COMPLETE
    state.clear(sender)
    
    return response


def is_logo_upload(body: str) -> bool:
    """Check if message contains a logo/image upload"""
    # ClickSend MMS includes media URLs
    # For now, check for common patterns
    lower = body.lower()
    return any(x in lower for x in ["logo", "my logo", "here's my logo", "heres my logo"])


async def handle_logo_upload(sender: str, body: str) -> str:
    """Handle logo image upload"""
    # TODO: Extract media URL from MMS and save
    response = ("Logo feature coming soon! For now, we'll generate quotes without a logo. "
               "Text your estimate anytime.")
    await send_sms(sender, response)
    return response
