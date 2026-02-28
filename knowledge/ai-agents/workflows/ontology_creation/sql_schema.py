"""
SQL schema introspection for ontology conversation workflow.

Provides safe, read-only introspection of user-provided SQL databases
(tables, columns, types, primary keys, foreign keys) so the ontology agent
can validate or suggest ontology based on the database structure.
Connection strings are never logged in full; use mask_connection_string().
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.engine import Engine
    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False
    create_engine = None
    inspect = None
    Engine = None


def mask_connection_string(connection_string: str) -> str:
    """Mask credentials in a connection string for safe logging.

    Examples:
        postgresql://user:secret@host/db -> postgresql://***@host/db
        Server=host;User Id=u;Password=p; -> Server=host;User Id=***;Password=***;
    """
    if not connection_string or len(connection_string) < 10:
        return "***"
    # URL-style: scheme://user:password@host/...
    url_match = re.match(r"^([^:]+://)([^@]+)(@.+)$", connection_string)
    if url_match:
        return f"{url_match.group(1)}***{url_match.group(3)}"
    # Key=value; style (e.g. SQL Server, ODBC)
    out = []
    for part in connection_string.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
            key_lower = key.strip().lower()
            if key_lower in ("password", "pwd", "secret", "user id", "uid", "username"):
                out.append(f"{key.strip()}=***")
            else:
                out.append(part)
        else:
            out.append(part)
        return "; ".join(out)


def _parse_sqlserver_connection_string(connection_string: str) -> Optional[str]:
    """Parse .NET/ADO.NET style SQL Server connection string into SQLAlchemy mssql+pyodbc URL.

    Handles: Server=...; Data Source=...; Initial Catalog=...; User ID=...; Password=...
    Returns None if the string does not look like a SQL Server key=value connection string.
    """
    s = connection_string.strip()
    if not s or "=" not in s:
        return None
    # Only treat as key=value if it has typical SQL Server keys (not a URL)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", s):
        return None
    parts = {}
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            key_lower = key.strip().lower()
            val = val.strip()
            if key_lower in ("server", "data source", "initial catalog", "user id", "uid", "username", "password", "pwd"):
                parts[key_lower] = val
    if "data source" in parts and "server" not in parts:
        parts["server"] = parts["data source"]
    if "server" not in parts and "data source" not in parts:
        return None
    host = parts.get("server") or parts.get("data source", "")
    # Server can be "tcp:host,1433" or "host"
    port = 1433
    if "," in host:
        host, port_str = host.rsplit(",", 1)
        host = host.strip()
        try:
            port = int(port_str.strip())
        except ValueError:
            pass
    if host.startswith("tcp:"):
        host = host[4:].strip()
    database = parts.get("initial catalog", "")
    user = parts.get("user id") or parts.get("uid") or parts.get("username", "")
    password = parts.get("password") or parts.get("pwd", "")
    if not host:
        return None
    # Build mssql+pyodbc URL; quote user and password for special characters
    user_quoted = quote_plus(user) if user else ""
    password_quoted = quote_plus(password) if password else ""
    if user_quoted and password_quoted:
        auth = f"{user_quoted}:{password_quoted}@"
    elif user_quoted:
        auth = f"{user_quoted}@"
    else:
        auth = ""
    # ODBC Driver 17 for SQL Server is common on Windows/Linux; 18 for Azure
    driver = "ODBC+Driver+17+for+SQL+Server"
    db_part = f"/{quote_plus(database)}" if database else ""
    query = f"driver={driver}"
    if ".database.windows.net" in host:
        query += "&Encrypt=yes&TrustServerCertificate=no"
    url = f"mssql+pyodbc://{auth}{host}:{port}{db_part}?{query}"
    return url


@dataclass
class ColumnInfo:
    """Column metadata from introspection."""
    name: str
    type_name: str
    nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_ref: Optional[str] = None  # "table.column" if FK


@dataclass
class TableInfo:
    """Table metadata from introspection."""
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class SqlSchemaSummary:
    """Summary of a SQL database schema for ontology suggestions."""
    tables: list[TableInfo] = field(default_factory=list)
    dialect: str = ""
    error: Optional[str] = None

    def to_agent_friendly_str(self) -> str:
        """Format for inclusion in agent context."""
        if self.error:
            return f"Schema introspection failed: {self.error}"
        lines = [f"Database dialect: {self.dialect or 'unknown'}", ""]
        for table in self.tables:
            lines.append(f"Table: {table.name}")
            for col in table.columns:
                pk = " (PK)" if col.is_primary_key else ""
                fk = f" (FK -> {col.foreign_key_ref})" if col.foreign_key_ref else ""
                lines.append(f"  - {col.name}: {col.type_name}, nullable={col.nullable}{pk}{fk}")
            lines.append("")
        return "\n".join(lines).strip()


def get_sql_schema(
    connection_string: str,
    dialect: Optional[str] = None,
) -> SqlSchemaSummary:
    """Introspect a SQL database and return a schema summary.

    Uses SQLAlchemy sync introspection. Does not log the connection string;
    uses mask_connection_string for any log lines.

    Args:
        connection_string: Database connection string (URL or key=value).
        dialect: Optional hint: "postgresql", "sqlserver", "mysql", etc.
                  If None, inferred from connection string where possible.

    Returns:
        SqlSchemaSummary with tables, columns, PKs, FKs; or error set on failure.
    """
    if not _SQLALCHEMY_AVAILABLE:
        return SqlSchemaSummary(
            error="sqlalchemy is not installed. Install with: pip install sqlalchemy"
        )

    masked = mask_connection_string(connection_string)
    logger.info("Introspecting SQL schema (connection masked): %s", masked)

    engine: Optional[Engine] = None
    try:
        # If it looks like a .NET/ADO.NET SQL Server connection string, convert to mssql+pyodbc URL
        conn_str = connection_string.strip()
        if dialect and dialect.lower() == "sqlserver":
            parsed = _parse_sqlserver_connection_string(conn_str)
            if parsed:
                conn_str = parsed
        elif not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", conn_str) and "=" in conn_str:
            parsed = _parse_sqlserver_connection_string(conn_str)
            if parsed:
                conn_str = parsed
        engine = create_engine(conn_str)

        insp = inspect(engine)
        dialect_name = engine.dialect.name if engine else "unknown"
        tables_out: list[TableInfo] = []

        for table_name in insp.get_table_names():
            columns_out: list[ColumnInfo] = []
            try:
                pk_constraint = insp.get_pk_constraint(table_name)
                pk_cols = {c for c in (pk_constraint or {}).get("constrained_columns") or []}
            except Exception:
                pk_cols = set()

            fk_refs: dict[str, str] = {}  # col_name -> "ref_table.ref_column"
            try:
                for fk in insp.get_foreign_keys(table_name):
                    constrained = fk.get("constrained_columns") or []
                    referred = fk.get("referred_table"), (fk.get("referred_columns") or [None])[0]
                    ref_str = f"{referred[0]}.{referred[1]}" if referred[1] else referred[0]
                    for col in constrained:
                        fk_refs[col] = ref_str
            except Exception:
                pass

            try:
                for col in insp.get_columns(table_name):
                    name = col["name"]
                    type_obj = col.get("type")
                    type_name = getattr(type_obj, "name", str(type_obj)) if type_obj else "unknown"
                    nullable = col.get("nullable", True)
                    columns_out.append(ColumnInfo(
                        name=name,
                        type_name=type_name,
                        nullable=nullable,
                        is_primary_key=name in pk_cols,
                        is_foreign_key=name in fk_refs,
                        foreign_key_ref=fk_refs.get(name),
                    ))
            except Exception as e:
                logger.warning("Failed to get columns for %s: %s", table_name, e)

            tables_out.append(TableInfo(name=table_name, columns=columns_out))

        return SqlSchemaSummary(tables=tables_out, dialect=dialect_name)
    except Exception as e:
        logger.warning("SQL schema introspection failed: %s", e, exc_info=False)
        return SqlSchemaSummary(
            dialect=dialect or "unknown",
            error=str(e),
        )
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
