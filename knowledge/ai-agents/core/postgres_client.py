"""
postgres_client.py - PostgreSQL database client for querying ontology Neo4j credentials.

This module provides async PostgreSQL access to query the app.ontologies table
for encrypted Neo4j passwords.
"""

import os
import logging
from typing import Optional
from app.config import Config

logger = logging.getLogger(__name__)

try:
    import asyncpg
    _ASYNCPG_AVAILABLE = True
except ImportError:
    _ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg library not available. PostgreSQL queries will not work.")


def _parse_connection_string(conn_str: str) -> dict:
    """
    Parse a PostgreSQL connection string in the format:
    Host=host;Port=port;Database=db;Username=user;Password=pass;SslMode=mode
    
    Returns:
        Dict with connection parameters
    """
    params = {}
    for part in conn_str.split(';'):
        if '=' in part:
            key, value = part.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'host':
                params['host'] = value
            elif key == 'port':
                params['port'] = int(value)
            elif key == 'database':
                params['database'] = value
            elif key == 'username':
                params['user'] = value
            elif key == 'password':
                params['password'] = value
            elif key == 'sslmode':
                params['ssl'] = value.lower() == 'require'
    
    return params


async def get_ontology_encrypted_password(ontology_id: str) -> Optional[str]:
    """
    Query the PostgreSQL database for the encrypted Neo4j password for an ontology.
    
    Args:
        ontology_id: UUID of the ontology
    
    Returns:
        Base64-encoded encrypted password string, or None if not found or error
    """
    if not _ASYNCPG_AVAILABLE:
        logger.error("asyncpg library not available. Cannot query PostgreSQL.")
        return None
    
    # Get connection string from config
    conn_str = os.getenv("DATABASE_CONNECTION_STRING")
    if not conn_str:
        logger.error("DATABASE_CONNECTION_STRING not configured")
        return None
    
    try:
        # Parse connection string
        conn_params = _parse_connection_string(conn_str)
        
        # Connect to database
        conn = await asyncpg.connect(**conn_params)
        
        try:
            # Query the app.ontologies table for neo4j_encrypted_password
            query = """
                SELECT neo4j_encrypted_password
                FROM app.ontologies
                WHERE ontology_id = $1
            """
            
            result = await conn.fetchrow(query, ontology_id)
            
            if result and result['neo4j_encrypted_password']:
                encrypted_password = result['neo4j_encrypted_password']
                logger.debug(f"Retrieved encrypted password for ontology {ontology_id}")
                return encrypted_password
            else:
                logger.debug(f"No encrypted password found for ontology {ontology_id}")
                return None
                
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Failed to query PostgreSQL for ontology {ontology_id}: {e}")
        return None
