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
    NEW = "new"                    # Fresh conversation
    NEED_CUSTOMER = "need_customer"  # Asked for customer name
    NEED_ITEMS = "need_items"      # Asked for line items/prices
    CONFIRMING = "confirming"      # Confirming before generating
    COMPLETE = "complete"          # Quote generated


@dataclass
class QuoteData:
    """Parsed quote information"""
    customer_name: Optional[str] = None
    items: List[Dict] = field(default_factory=list)  # [{description, amount}]
    notes: Optional[str] = None
    total: Optional[float] = None
    
    def is_complete(self) -> bool:
        """Check if we have enough to generate a quote"""
        return bool(self.customer_name and self.items and len(self.items) > 0)
    
    def calculate_total(self) -> float:
        """Sum up line items"""
        self.total = sum(float(item.get("amount") or 0) for item in self.items)
        return self.total


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
        # Clean phone number
        phone = self._normalize_phone(phone)
        
        if phone in self.conversations:
            convo = self.conversations[phone]
            # Reset if expired
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
        # Strip everything except digits and leading +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        if not cleaned.startswith('+'):
            cleaned = '+1' + cleaned  # Assume US
        return cleaned
    
    def _save(self):
        """Persist state to disk"""
        if not self.persist_path:
            return
        # TODO: Implement JSON serialization
        pass
    
    def _load(self):
        """Load state from disk"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        # TODO: Implement JSON deserialization
        pass


# Global state instance
state = ConversationState()
