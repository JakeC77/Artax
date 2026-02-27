"""
Estimate parser using LLM
Extracts customer name, line items, and prices from freeform text
"""

import os
import json
import re
from typing import Optional
import httpx

from .state import QuoteData


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

PARSE_PROMPT = """Extract quote information from this text message. Return JSON only.

Text: {text}

Extract:
- customer_name: The customer/client name (null if not found)  
- items: Array of {{description: string, amount: number}} for each line item
- notes: Any additional notes or terms (null if none)

Rules:
- Parse prices flexibly: "$450", "450", "four fifty", "~700" all work
- If price is a range or approximate, use the middle/stated value
- Split combined items if possible ("deck and railing $700" → keep as one if price isn't split)
- Customer name might be at start, "for John", "John Smith -", etc.
- Return valid JSON only, no markdown

Example input: "John Smith deck repair 450 new railing 275 materials 180"
Example output: {{"customer_name": "John Smith", "items": [{{"description": "Deck repair", "amount": 450}}, {{"description": "New railing", "amount": 275}}, {{"description": "Materials", "amount": 180}}], "notes": null}}

Return JSON:"""


async def parse_estimate(text: str, existing: Optional[QuoteData] = None) -> QuoteData:
    """
    Parse freeform estimate text into structured QuoteData
    Uses LLM for flexible parsing, falls back to regex
    """
    # Try LLM parsing first
    if ANTHROPIC_API_KEY:
        result = await parse_with_llm(text)
        if result:
            return result
    
    # Fallback to regex parsing
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
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "messages": [{
                        "role": "user", 
                        "content": PARSE_PROMPT.format(text=text)
                    }]
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                print(f"LLM parse error: {response.status_code}")
                return None
            
            data = response.json()
            content = data["content"][0]["text"]
            
            # Parse JSON from response
            parsed = json.loads(content)
            
            return QuoteData(
                customer_name=parsed.get("customer_name"),
                items=parsed.get("items", []),
                notes=parsed.get("notes")
            )
    except Exception as e:
        print(f"LLM parse exception: {e}")
        return None


def parse_with_regex(text: str, existing: Optional[QuoteData] = None) -> QuoteData:
    """
    Fallback regex-based parsing
    Handles both "item $50" and "50 items" patterns
    """
    result = QuoteData()
    
    # Try to extract customer name (common patterns)
    name_patterns = [
        r'^([A-Z][a-z]+ [A-Z][a-z]+)',  # "John Smith" at start
        r'for ([A-Z][a-z]+ [A-Z][a-z]+)',  # "for John Smith"
        r'^([A-Z][a-z]+) -',  # "John -"
        r'^([A-Z][a-z]+ [A-Z][a-z]+)\s*-',  # "John Smith -" or "John Smith-"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            result.customer_name = match.group(1)
            break
    
    # Pattern 1: "description $123" or "description 123"
    pattern1 = r'([a-zA-Z][a-zA-Z\s]+?)\s*\$?\s*(\d+(?:\.\d{2})?)\s*(?:dollars?|each|total)?'
    
    # Pattern 2: "123 description" or "$123 description" or "2 widgets"  
    pattern2 = r'(\d+)\s*(?:x\s*)?([a-zA-Z][a-zA-Z\s]+?)\s*(?:@|at|for|-)?\s*\$?(\d+(?:\.\d{2})?)?'
    
    # Pattern 3: Simple "NUMBER description NUMBER" like "20 shirts 50"
    pattern3 = r'(\d+)\s+([a-zA-Z][a-zA-Z\s]+?)\s+\$?(\d+)'
    
    items_found = []
    
    # Try pattern 1: description then price
    matches1 = re.findall(pattern1, text, re.IGNORECASE)
    for desc, amount in matches1:
        desc = desc.strip()
        if result.customer_name and desc.lower() in result.customer_name.lower():
            continue
        if len(desc) < 2 or desc.lower() in ['for', 'at', 'the', 'and', 'or']:
            continue
        items_found.append({
            "description": desc.title(),
            "amount": float(amount)
        })
    
    # Try pattern 3 if pattern 1 didn't find much: "20 shirts 50"
    if len(items_found) < 1:
        matches3 = re.findall(pattern3, text, re.IGNORECASE)
        for qty, desc, price in matches3:
            desc = desc.strip()
            if result.customer_name and desc.lower() in result.customer_name.lower():
                continue
            if len(desc) < 2:
                continue
            # Format as "20 shirts" or just "shirts" depending on qty
            if int(qty) > 1:
                full_desc = f"{qty} {desc}"
            else:
                full_desc = desc
            items_found.append({
                "description": full_desc.title(),
                "amount": float(price)
            })
    
    result.items = items_found
    return result
