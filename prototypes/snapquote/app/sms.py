"""
SMS handling for SnapQuote
Conversational quote builder via text
"""

import os
import httpx
from typing import Optional

from .state import state, ConvoStage, QuoteData
from .parser import parse_estimate
from .pdf_gen import generate_quote_pdf
from .logos import get_logo_path
from .tax import get_tax_rate, format_tax_rate


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
    """Main inbound SMS handler with conversational flow"""
    print(f"Handling SMS from {sender}: {body}", flush=True)
    
    lower_body = body.lower().strip()
    
    # Reset commands
    reset_keywords = ["reset", "start over", "cancel", "new", "new quote", "start", "begin", "clear"]
    if lower_body in reset_keywords:
        state.clear(sender)
        response = "Hey! Let's build a quote. Who's the customer?"
        await send_sms(sender, response)
        return response
    
    # Help command
    if lower_body in ["help", "?", "how"]:
        response = ("SnapQuote here! I'll walk you through creating a professional quote.\n\n"
                   "Just text 'new' to get started, and I'll ask you a few quick questions.\n\n"
                   "Or if you're in a hurry, send everything at once like:\n"
                   "John Smith, 123 Main St Seattle WA, deck repair $500 - refinishing the back deck")
        await send_sms(sender, response)
        return response
    
    # Get or create conversation
    convo = state.get(sender)
    convo.raw_messages.append(body)
    
    # Route based on conversation stage
    if convo.stage == ConvoStage.NEW:
        return await handle_new_conversation(sender, body, convo)
    elif convo.stage == ConvoStage.NEED_CUSTOMER:
        return await handle_customer_name(sender, body, convo)
    elif convo.stage == ConvoStage.NEED_ADDRESS:
        return await handle_address(sender, body, convo)
    elif convo.stage == ConvoStage.NEED_ITEMS:
        return await handle_items(sender, body, convo)
    elif convo.stage == ConvoStage.NEED_DESCRIPTION:
        return await handle_description(sender, body, convo)
    else:
        return await handle_new_conversation(sender, body, convo)


async def handle_new_conversation(sender: str, body: str, convo) -> str:
    """Handle first message - try to parse or start guided flow"""
    
    parsed = await parse_estimate(body, None)
    
    if parsed.customer_name:
        convo.quote.customer_name = parsed.customer_name
    if parsed.customer_address:
        convo.quote.customer_address = parsed.customer_address
    if parsed.items:
        convo.quote.items = parsed.items
    if parsed.project_description:
        convo.quote.project_description = parsed.project_description
    
    missing = convo.quote.get_missing()
    
    if not missing:
        return await generate_and_send_quote(sender, convo)
    
    return await ask_for_missing(sender, convo, missing[0])


async def ask_for_missing(sender: str, convo, field: str) -> str:
    """Ask for a specific missing field conversationally"""
    
    if field == "customer_name":
        convo.stage = ConvoStage.NEED_CUSTOMER
        response = "Hey! Let's build a quote. Who's the customer?"
        
    elif field == "customer_address":
        convo.stage = ConvoStage.NEED_ADDRESS
        name = convo.quote.customer_name
        response = f"Got it — quote for {name}. What's their address? I'll use it to calculate sales tax."
        
    elif field == "items":
        convo.stage = ConvoStage.NEED_ITEMS
        if convo.quote.customer_address:
            response = "Perfect. Now what are you quoting them for? Just list the items and prices, like:\n\nDeck repair $450\nRailing $275"
        else:
            response = "What's the work and pricing? List items like:\n\nDeck repair $450\nRailing $275"
            
    elif field == "project_description":
        convo.stage = ConvoStage.NEED_DESCRIPTION
        items = convo.quote.items
        total = sum(float(i.get("amount") or 0) for i in items)
        item_names = ", ".join(i['description'] for i in items[:3])
        response = f"Nice — {item_names} for ${total:,.0f}. Last thing: give me a quick description of the project (one line is fine)."
        
    else:
        response = "Hmm, something got confused. Text 'new' to start fresh!"
    
    state.update(sender, convo)
    await send_sms(sender, response)
    return response


async def handle_customer_name(sender: str, body: str, convo) -> str:
    """Handle customer name input"""
    # Check if they gave us more than just a name
    parsed = await parse_estimate(body, None)
    
    if parsed.customer_name:
        convo.quote.customer_name = parsed.customer_name
    else:
        convo.quote.customer_name = body.strip().title()
    
    if parsed.customer_address:
        convo.quote.customer_address = parsed.customer_address
    if parsed.items:
        convo.quote.items = parsed.items
    if parsed.project_description:
        convo.quote.project_description = parsed.project_description
    
    missing = convo.quote.get_missing()
    if not missing:
        return await generate_and_send_quote(sender, convo)
    
    return await ask_for_missing(sender, convo, missing[0])


async def handle_address(sender: str, body: str, convo) -> str:
    """Handle address input and lookup tax rate"""
    convo.quote.customer_address = body.strip()
    
    tax_rate, state_abbrev = get_tax_rate(body)
    if tax_rate is not None:
        convo.quote.tax_rate = tax_rate
        print(f"Tax rate for {state_abbrev}: {format_tax_rate(tax_rate)}", flush=True)
    
    missing = convo.quote.get_missing()
    if not missing:
        return await generate_and_send_quote(sender, convo)
    
    return await ask_for_missing(sender, convo, missing[0])


async def handle_items(sender: str, body: str, convo) -> str:
    """Handle line items input"""
    parsed = await parse_estimate(body, None)
    
    if parsed.items:
        convo.quote.items = parsed.items
    else:
        import re
        pattern = r'([a-zA-Z][a-zA-Z\s]+?)\s*\$?\s*(\d+(?:\.\d{2})?)'
        matches = re.findall(pattern, body, re.IGNORECASE)
        for desc, amount in matches:
            convo.quote.items.append({
                "description": desc.strip().title(),
                "amount": float(amount)
            })
    
    if not convo.quote.items:
        response = "I couldn't quite parse that. Try listing each item with a price, like:\n\nPainting $800\nMaterials $200"
        await send_sms(sender, response)
        return response
    
    if parsed.project_description:
        convo.quote.project_description = parsed.project_description
    
    missing = convo.quote.get_missing()
    if not missing:
        return await generate_and_send_quote(sender, convo)
    
    return await ask_for_missing(sender, convo, missing[0])


async def handle_description(sender: str, body: str, convo) -> str:
    """Handle project description input"""
    convo.quote.project_description = body.strip()
    
    missing = convo.quote.get_missing()
    if not missing:
        return await generate_and_send_quote(sender, convo)
    
    return await ask_for_missing(sender, convo, missing[0])


async def generate_and_send_quote(sender: str, convo) -> str:
    """Generate PDF and send link"""
    quote = convo.quote
    quote.calculate_total()
    
    logo_path = get_logo_path(sender)
    
    quote_id = generate_quote_pdf(
        customer_name=quote.customer_name,
        customer_address=quote.customer_address,
        items=quote.items,
        project_description=quote.project_description,
        subtotal=quote.total,
        tax_rate=quote.tax_rate,
        tax_amount=quote.tax_amount,
        total=quote.grand_total,
        notes=quote.notes,
        logo_path=logo_path
    )
    
    quote_url = f"{BASE_URL}/quote/{quote_id}"
    
    # Friendly completion message
    if quote.tax_rate:
        tax_pct = f"{quote.tax_rate * 100:.1f}%"
        response = (f"Done! Here's the quote for {quote.customer_name}:\n\n"
                   f"Subtotal: ${quote.total:,.2f}\n"
                   f"Tax ({tax_pct}): ${quote.tax_amount:,.2f}\n"
                   f"Total: ${quote.grand_total:,.2f}\n\n"
                   f"{quote_url}\n\n"
                   f"Send that link to your customer. Text 'new' when you're ready for another!")
    else:
        response = (f"Done! Here's the quote for {quote.customer_name}:\n\n"
                   f"Total: ${quote.grand_total:,.2f}\n\n"
                   f"{quote_url}\n\n"
                   f"Send that link to your customer. Text 'new' when you're ready for another!")
    
    await send_sms(sender, response)
    
    convo.stage = ConvoStage.COMPLETE
    state.clear(sender)
    
    print(f"Quote generated: {quote_id}", flush=True)
    return response
