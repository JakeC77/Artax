"""
Estimate parser using LLM
Extracts customer info, line items, and prices from freeform text
"""

import os
import json
import re
from typing import Optional
import httpx

from .state import QuoteData


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

PARSE_PROMPT = """Extract quote information from this contractor's text message. Return JSON only.

Text: {text}

Extract:
- customer_name: The customer/client name (null if not found)
- customer_address: Full address if provided (null if not found)
- items: Array of {{description: string, amount: number}} for EACH separate line item. 
  If multiple items are listed (e.g. "burgers $5, shakes $4, fries $3"), extract ALL of them as separate objects.
  If a quantity is given (e.g. "55 burgers $5 each"), calculate the total (55 * 5 = 275) and use that as the amount.
  If an item has no price, set amount to 0.
- project_description: Brief description of the work/project (null if not found)
- notes: Any additional notes or terms (null if none)

Rules:
- ALWAYS extract ALL line items — never merge multiple items into one
- Parse prices flexibly: "$450", "450", "four fifty" all work
- "X items @ $Y each" or "X items $Y each" → amount = X * Y
- Customer name might be "for John", "John Smith -", etc.
- Return valid JSON only, no markdown

Example input: "55 burgers $2 each, 55 shakes $3 each, 55 fries $1.50 each"
Example output: {{"customer_name": null, "customer_address": null, "items": [{{"description": "Burgers (x55)", "amount": 110.0}}, {{"description": "Shakes (x55)", "amount": 165.0}}, {{"description": "Fries (x55)", "amount": 82.5}}], "project_description": null, "notes": null}}

Example input: "John Smith, 123 Main St Seattle WA - deck repair $450, railing $275, staining $150"
Example output: {{"customer_name": "John Smith", "customer_address": "123 Main St Seattle WA", "items": [{{"description": "Deck repair", "amount": 450}}, {{"description": "Railing", "amount": 275}}, {{"description": "Staining", "amount": 150}}], "project_description": null, "notes": null}}

Return JSON:"""


async def parse_estimate(text: str, existing: Optional[QuoteData] = None) -> QuoteData:
    """Parse freeform estimate text into structured QuoteData"""
    if ANTHROPIC_API_KEY:
        result = await parse_with_llm(text)
        if result:
            return result
    
    return parse_with_regex(text, existing)


async def parse_with_llm(text: str) -> Optional[QuoteData]:
    """Parse using Claude API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 800,
                    "messages": [{
                        "role": "user", 
                        "content": PARSE_PROMPT.format(text=text)
                    }]
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                print(f"LLM parse error: {response.status_code} {response.text[:200]}", flush=True)
                return None
            
            data = response.json()
            content = data["content"][0]["text"]
            
            # Strip markdown code fences if present
            content = re.sub(r'^```(?:json)?\s*', '', content.strip())
            content = re.sub(r'\s*```$', '', content)

            parsed = json.loads(content)
            
            return QuoteData(
                customer_name=parsed.get("customer_name"),
                customer_address=parsed.get("customer_address"),
                items=parsed.get("items", []),
                project_description=parsed.get("project_description"),
                notes=parsed.get("notes")
            )
    except Exception as e:
        print(f"LLM parse exception: {e}", flush=True)
        return None


def parse_with_regex(text: str, existing: Optional[QuoteData] = None) -> QuoteData:
    """Fallback regex-based parsing"""
    result = QuoteData()
    
    # Customer name patterns
    name_patterns = [
        r'^([A-Z][a-z]+ [A-Z][a-z]+)',
        r'for ([A-Z][a-z]+ [A-Z][a-z]+)',
        r'^([A-Z][a-z]+ [A-Z][a-z]+)\s*[-,]',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            result.customer_name = match.group(1)
            break
    
    # Address pattern
    addr_pattern = r'(\d+[^,]+,\s*[^,]+,?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)'
    addr_match = re.search(addr_pattern, text)
    if addr_match:
        result.customer_address = addr_match.group(1)
    
    # Item patterns — try to get all matches
    pattern1 = r'([a-zA-Z][a-zA-Z\s]+?)\s*\$\s*(\d+(?:\.\d{2})?)'
    matches1 = re.findall(pattern1, text, re.IGNORECASE)
    for desc, amount in matches1:
        desc = desc.strip()
        if result.customer_name and desc.lower() in result.customer_name.lower():
            continue
        if len(desc) < 2 or desc.lower() in ['for', 'at', 'the', 'and']:
            continue
        result.items.append({
            "description": desc.title(),
            "amount": float(amount)
        })
    
    # Qty × item pattern: "55 burgers $2"
    if not result.items:
        pattern2 = r'(\d+)\s+([a-zA-Z][a-zA-Z\s]+?)\s+\$?(\d+(?:\.\d{2})?)'
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        for qty, desc, price in matches2:
            desc = desc.strip()
            if len(desc) < 2:
                continue
            full_desc = f"{desc.title()} (x{qty})"
            result.items.append({
                "description": full_desc,
                "amount": round(int(qty) * float(price), 2)
            })
    
    return result
