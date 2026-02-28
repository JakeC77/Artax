"""
Conversation state management for SnapQuote
Tracks ongoing quote conversations by phone number
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class ConvoStage(Enum):
    """Stages of a quote conversation"""
    NEW = "new"
    NEED_CUSTOMER = "need_customer"
    NEED_ADDRESS = "need_address"
    NEED_ITEMS = "need_items"
    NEED_DESCRIPTION = "need_description"
    CONFIRMING = "confirming"
    COMPLETE = "complete"


@dataclass
class QuoteData:
    """Parsed quote information"""
    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    items: List[Dict] = field(default_factory=list)  # [{description, amount}]
    project_description: Optional[str] = None
    notes: Optional[str] = None
    total: Optional[float] = None
    tax_rate: Optional[float] = None  # e.g., 0.08 for 8%
    tax_amount: Optional[float] = None
    grand_total: Optional[float] = None
    
    def is_complete(self) -> bool:
        """Check if we have enough to generate a quote"""
        has_name = bool(self.customer_name)
        has_address = bool(self.customer_address)
        has_items = bool(self.items and len(self.items) > 0)
        has_description = bool(self.project_description)
        return has_name and has_address and has_items and has_description
    
    def get_missing(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.customer_name:
            missing.append("customer_name")
        if not self.customer_address:
            missing.append("customer_address")
        if not self.items or len(self.items) == 0:
            missing.append("items")
        if not self.project_description:
            missing.append("project_description")
        return missing
    
    def calculate_total(self) -> float:
        """Sum up line items and apply tax"""
        self.total = sum(float(item.get("amount") or 0) for item in self.items)
        if self.tax_rate:
            self.tax_amount = round(self.total * self.tax_rate, 2)
            self.grand_total = round(self.total + self.tax_amount, 2)
        else:
            self.tax_amount = 0
            self.grand_total = self.total
        return self.grand_total


@dataclass 
class Conversation:
    """Tracks a single conversation with a phone number"""
    phone: str
    stage: ConvoStage = ConvoStage.NEW
    quote: QuoteData = field(default_factory=QuoteData)
    raw_messages: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if conversation has timed out"""
        return datetime.utcnow() - self.updated_at > timedelta(minutes=timeout_minutes)
    
    def touch(self):
        """Update last activity time"""
        self.updated_at = datetime.utcnow()


class ConversationState:
    """
    Manages all active conversations
    Simple in-memory store with optional persistence
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        self.conversations: Dict[str, Conversation] = {}
        self.persist_path = persist_path
        self._load()
    
    def get(self, phone: str) -> Conversation:
        """Get or create conversation for a phone number"""
        phone = self._normalize_phone(phone)
        
        if phone in self.conversations:
            convo = self.conversations[phone]
            if convo.is_expired():
                convo = Conversation(phone=phone)
                self.conversations[phone] = convo
            convo.touch()
        else:
            convo = Conversation(phone=phone)
            self.conversations[phone] = convo
        
        self._save()
        return convo
    
    def update(self, phone: str, convo: Conversation):
        """Update a conversation"""
        phone = self._normalize_phone(phone)
        convo.touch()
        self.conversations[phone] = convo
        self._save()
    
    def clear(self, phone: str):
        """Clear a conversation (after quote complete)"""
        phone = self._normalize_phone(phone)
        if phone in self.conversations:
            del self.conversations[phone]
            self._save()
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format"""
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not cleaned.startswith('+'):
            cleaned = '+1' + cleaned
        return cleaned
    
    def _save(self):
        if not self.persist_path:
            return
    
    def _load(self):
        if not self.persist_path or not os.path.exists(self.persist_path):
            return


# Global state instance
state = ConversationState()
