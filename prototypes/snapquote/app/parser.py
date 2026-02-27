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
                    "model": "claude-3-haiku-20240307",
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
    Less flexible but works without API
    """
    result = QuoteData()
    
    # Try to extract customer name (common patterns)
    name_patterns = [
        r'^([A-Z][a-z]+ [A-Z][a-z]+)',  # "John Smith" at start
        r'for ([A-Z][a-z]+ [A-Z][a-z]+)',  # "for John Smith"
        r'^([A-Z][a-z]+) -',  # "John -"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            result.customer_name = match.group(1)
            break
    
    # Extract price patterns: "item $123" or "item 123"
    # Match: description followed by $ and numbers, or just numbers at word boundary
    item_pattern = r'([a-zA-Z][a-zA-Z\s]+?)\s*\$?\s*(\d+(?:\.\d{2})?)'
    matches = re.findall(item_pattern, text)
    
    for desc, amount in matches:
        desc = desc.strip()
        # Skip if description looks like a name we already captured
        if result.customer_name and desc.lower() in result.customer_name.lower():
            continue
        # Skip very short descriptions
        if len(desc) < 2:
            continue
        
        result.items.append({
            "description": desc.title(),
            "amount": float(amount)
        })
    
    return result
