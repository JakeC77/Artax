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
BASE_URL = os.getenv("BASE_URL", "https://snapquote.haventechsolutions.com")


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
        print(f"SMS send response: {response.status_code}", flush=True)
        return response.status_code == 200


async def handle_inbound_sms(sender: str, body: str) -> Optional[str]:
    """
    Main inbound SMS handler
    Routes through conversation state machine
    """
    print(f"Handling SMS from {sender}: {body}", flush=True)
    
    # Check for special commands FIRST
    lower_body = body.lower().strip()
    
    # Reset commands
    reset_keywords = ["reset", "start over", "cancel", "new", "new quote", "start", "begin", "clear"]
    if lower_body in reset_keywords:
        state.clear(sender)
        response = "Starting fresh! Text me your estimate like: John Smith - deck repair $450, railing $275"
        await send_sms(sender, response)
        return response
    
    # Help command
    if lower_body in ["help", "?", "how", "what", "huh"]:
        state.clear(sender)  # Also clear state on confusion
        response = ("SnapQuote turns texts into pro PDF quotes!\n\n"
                   "Text like this:\n"
                   "John Smith - deck repair $450, railing $275\n\n"
                   "I'll send back a link to a professional quote.")
        await send_sms(sender, response)
        return response
    
    # Check for logo upload
    if is_logo_upload(body):
        return await handle_logo_upload(sender, body)
    
    # Parse the message
    parsed = await parse_estimate(body, None)  # Don't pass existing - parse fresh
    
    print(f"Parsed: customer={parsed.customer_name}, items={len(parsed.items)}, complete={parsed.is_complete()}", flush=True)
    
    # If message didn't parse to anything useful, ask for clarification
    if not parsed.customer_name and not parsed.items:
        state.clear(sender)  # Clear any old state
        response = ("I didn't catch that. Text your estimate like:\n"
                   "John Smith - deck repair $450, railing $275\n\n"
                   "Or text 'help' for more info.")
        await send_sms(sender, response)
        return response
    
    # Get or create conversation
    convo = state.get(sender)
    
    # Update conversation with NEW parsed data
    if parsed.customer_name:
        convo.quote.customer_name = parsed.customer_name
    if parsed.items:
        convo.quote.items = parsed.items  # Replace, don't extend
    if parsed.notes:
        convo.quote.notes = parsed.notes
    
    convo.raw_messages.append(body)
    
    # Determine response based on what we have
    response = await determine_response(sender, convo)
    state.update(sender, convo)
    
    return response


async def determine_response(sender: str, convo) -> str:
    """Decide what to say based on conversation state"""
    quote = convo.quote
    
    # Check what's missing
    missing_customer = not quote.customer_name
    missing_items = not quote.items or len(quote.items) == 0
    
    print(f"Determining response: customer={quote.customer_name}, items={len(quote.items) if quote.items else 0}", flush=True)
    
    # If we have everything, generate the quote
    if quote.is_complete():
        return await generate_and_send_quote(sender, convo)
    
    # Ask for missing info
    if missing_items:
        convo.stage = ConvoStage.NEED_ITEMS
        if quote.customer_name:
            response = f"Got it for {quote.customer_name}. What are the items and prices?"
        else:
            response = "What items and prices for the quote? Like: deck repair $450, railing $275"
        await send_sms(sender, response)
        return response
    
    if missing_customer:
        convo.stage = ConvoStage.NEED_CUSTOMER
        items_summary = ", ".join(f"{i['description']} ${i['amount']:.0f}" for i in quote.items[:3])
        response = f"Got: {items_summary}. Customer name for the quote?"
        await send_sms(sender, response)
        return response
    
    # Fallback
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
    
    print(f"Quote generated: {quote_id}", flush=True)
    return response


def is_logo_upload(body: str) -> bool:
    """Check if message contains a logo/image upload"""
    lower = body.lower()
    return any(x in lower for x in ["logo", "my logo", "here's my logo", "heres my logo"])


async def handle_logo_upload(sender: str, body: str) -> str:
    """Handle logo image upload"""
    response = ("Logo feature coming soon! For now, we'll generate quotes without a logo. "
               "Text your estimate anytime.")
    await send_sms(sender, response)
    return response
