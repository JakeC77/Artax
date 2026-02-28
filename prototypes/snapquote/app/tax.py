"""
Sales tax lookup for SnapQuote
Based on customer address (state-level for US)
"""

import re
from typing import Optional, Tuple

# US State sales tax rates (2024 averages - state + avg local)
# Source: Tax Foundation
US_STATE_TAX_RATES = {
    "AL": 0.0922, "AK": 0.0176, "AZ": 0.0840, "AR": 0.0947, "CA": 0.0868,
    "CO": 0.0777, "CT": 0.0635, "DE": 0.0000, "FL": 0.0701, "GA": 0.0732,
    "HI": 0.0444, "ID": 0.0603, "IL": 0.0882, "IN": 0.0700, "IA": 0.0694,
    "KS": 0.0871, "KY": 0.0600, "LA": 0.0955, "ME": 0.0550, "MD": 0.0600,
    "MA": 0.0625, "MI": 0.0600, "MN": 0.0749, "MS": 0.0707, "MO": 0.0825,
    "MT": 0.0000, "NE": 0.0694, "NV": 0.0823, "NH": 0.0000, "NJ": 0.0660,
    "NM": 0.0783, "NY": 0.0852, "NC": 0.0698, "ND": 0.0696, "OH": 0.0723,
    "OK": 0.0895, "OR": 0.0000, "PA": 0.0634, "RI": 0.0700, "SC": 0.0744,
    "SD": 0.0640, "TN": 0.0955, "TX": 0.0820, "UT": 0.0719, "VT": 0.0624,
    "VA": 0.0575, "WA": 0.0929, "WV": 0.0652, "WI": 0.0543, "WY": 0.0536,
    "DC": 0.0600,
}

# State name to abbreviation mapping
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC", "d.c.": "DC",
}


def extract_state_from_address(address: str) -> Optional[str]:
    """Extract state abbreviation from an address string"""
    address_upper = address.upper().strip()
    address_lower = address.lower().strip()
    
    # Try to find state abbreviation (2 letters before ZIP or at end)
    # Pattern: ", XX 12345" or ", XX" or " XX 12345"
    patterns = [
        r',?\s+([A-Z]{2})\s+\d{5}',  # ", CA 90210" or " CA 90210"
        r',?\s+([A-Z]{2})$',          # ", CA" at end
        r'\b([A-Z]{2})\s+\d{5}',      # "CA 90210" anywhere
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address_upper)
        if match:
            abbrev = match.group(1)
            if abbrev in US_STATE_TAX_RATES:
                return abbrev
    
    # Try to find state name
    for state_name, abbrev in STATE_NAMES.items():
        if state_name in address_lower:
            return abbrev
    
    return None


def get_tax_rate(address: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Get sales tax rate based on address.
    Returns (tax_rate, state_abbrev) or (None, None) if not found.
    """
    state = extract_state_from_address(address)
    if state and state in US_STATE_TAX_RATES:
        return US_STATE_TAX_RATES[state], state
    return None, None


def format_tax_rate(rate: float) -> str:
    """Format tax rate as percentage string"""
    return f"{rate * 100:.2f}%"
