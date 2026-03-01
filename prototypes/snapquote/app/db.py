"""
SQLite persistence for SnapQuote
Stores completed quotes for admin dashboard + history
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


# DB lives in data/ dir relative to app root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "snapquote.db")


def _get_conn() -> sqlite3.Connection:
    """Get a sqlite3 connection with row_factory set"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Call at app startup."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id     TEXT NOT NULL UNIQUE,
                phone        TEXT NOT NULL,
                customer_name    TEXT,
                customer_address TEXT,
                project_description TEXT,
                items_json   TEXT,
                total        REAL,
                grand_total  REAL,
                tax_rate     REAL,
                pdf_path     TEXT,
                created_at   TEXT NOT NULL
            )
        """)
        conn.commit()
        print(f"[db] initialized at {DB_PATH}", flush=True)
    finally:
        conn.close()


def save_quote(quote_id: str, phone: str, quote_data) -> bool:
    """
    Persist a completed quote to SQLite.
    quote_data is a QuoteData instance from state.py
    """
    try:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO quotes
                  (quote_id, phone, customer_name, customer_address,
                   project_description, items_json, total, grand_total,
                   tax_rate, pdf_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote_id,
                phone,
                getattr(quote_data, "customer_name", None),
                getattr(quote_data, "customer_address", None),
                getattr(quote_data, "project_description", None),
                json.dumps(getattr(quote_data, "items", []) or []),
                getattr(quote_data, "total", None),
                getattr(quote_data, "grand_total", None),
                getattr(quote_data, "tax_rate", None),
                f"quotes/{quote_id}.pdf",
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
            print(f"[db] saved quote {quote_id}", flush=True)
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[db] ERROR saving quote {quote_id}: {e}", flush=True)
        return False


def get_all_quotes() -> List[Dict[str, Any]]:
    """Return all quotes ordered by newest first"""
    try:
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM quotes ORDER BY created_at DESC
            """).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["items"] = json.loads(d.get("items_json") or "[]")
                except Exception:
                    d["items"] = []
                result.append(d)
            return result
        finally:
            conn.close()
    except Exception as e:
        print(f"[db] ERROR fetching quotes: {e}", flush=True)
        return []


def get_quote(quote_id: str) -> Optional[Dict[str, Any]]:
    """Return a single quote by quote_id"""
    try:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM quotes WHERE quote_id = ?", (quote_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["items"] = json.loads(d.get("items_json") or "[]")
            except Exception:
                d["items"] = []
            return d
        finally:
            conn.close()
    except Exception as e:
        print(f"[db] ERROR fetching quote {quote_id}: {e}", flush=True)
        return None
