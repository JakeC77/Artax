"""
Logo management for SnapQuote
Store and retrieve contractor logos by phone number
"""

import os
from typing import Optional


LOGOS_DIR = os.getenv("LOGOS_DIR", "logos")


def get_logo_path(phone: str) -> Optional[str]:
    """Get logo path for a phone number if it exists"""
    phone_clean = ''.join(c for c in phone if c.isdigit())
    
    # Check for common image formats
    for ext in ['png', 'jpg', 'jpeg', 'webp']:
        path = os.path.join(LOGOS_DIR, f"{phone_clean}.{ext}")
        if os.path.exists(path):
            return path
    
    return None


def save_logo(phone: str, image_data: bytes, extension: str = 'png') -> str:
    """Save logo image for a phone number"""
    os.makedirs(LOGOS_DIR, exist_ok=True)
    
    phone_clean = ''.join(c for c in phone if c.isdigit())
    path = os.path.join(LOGOS_DIR, f"{phone_clean}.{extension}")
    
    with open(path, 'wb') as f:
        f.write(image_data)
    
    return path


def delete_logo(phone: str) -> bool:
    """Delete logo for a phone number"""
    path = get_logo_path(phone)
    if path and os.path.exists(path):
        os.remove(path)
        return True
    return False
