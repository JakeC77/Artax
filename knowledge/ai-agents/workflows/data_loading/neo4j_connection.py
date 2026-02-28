"""
neo4j_connection.py - Fetch and decrypt per-ontology Neo4j connection details.

This module fetches Neo4j connection details from the ontology record:
1. Uses GraphQL to get uri and username
2. Uses PostgreSQL to get encrypted password
3. Decrypts the password using AES-256-CBC
4. Returns connection details or None to fall back to default config
"""

import logging
from typing import Optional, Dict
from app.config import Config
from app.core.authenticated_graphql_client import run_graphql
from app.core.postgres_client import get_ontology_encrypted_password
from app.workflows.data_loading.neo4j_decrypt import decrypt_ontology_neo4j_password

logger = logging.getLogger(__name__)

# GraphQL query to fetch ontology Neo4j connection details
GET_ONTOLOGY_QUERY = """
query GetOntology($ontologyId: UUID!) {
  ontologyById(ontologyId: $ontologyId) {
    ontologyId
    tenantId
    name
    description
    semVer
    createdOn
    createdBy
    lastEdit
    lastEditedBy
    status
    runId
    jsonUri
    neo4jConnection {
      uri
      username
    }
  }
}
""".strip()


async def get_ontology_neo4j_connection(
    ontology_id: str,
    tenant_id: str
) -> Optional[Dict[str, str]]:
    """
    Fetch and decrypt Neo4j connection details for an ontology.
    
    Args:
        ontology_id: UUID of the ontology
        tenant_id: Tenant ID for GraphQL authentication
    
    Returns:
        Dict with 'uri', 'username', 'password' keys if per-ontology Neo4j is configured,
        None if ontology doesn't have per-ontology Neo4j (should use default config)
    """
    try:
        # Step 1: Fetch ontology details from GraphQL (includes uri and username)
        try:
            result = await run_graphql(
                GET_ONTOLOGY_QUERY,
                {"ontologyId": ontology_id},
                tenant_id=tenant_id
            )
            
            ontology = result.get("ontologyById")
            if not ontology:
                logger.warning(f"Ontology {ontology_id} not found via GraphQL")
                return None
            
            neo4j_connection = ontology.get("neo4jConnection")
            if not neo4j_connection:
                logger.debug(f"Ontology {ontology_id} has no neo4jConnection configured")
                return None
            
            uri = neo4j_connection.get("uri")
            username = neo4j_connection.get("username")
            
            # Check if uri and username are present and non-empty
            if not uri or not username:
                logger.debug(f"Ontology {ontology_id} has incomplete Neo4j connection (missing uri or username)")
                return None
                
        except Exception as e:
            logger.error(f"Failed to fetch ontology from GraphQL: {e}")
            return None
        
        # Step 2: Fetch encrypted password from PostgreSQL
        encrypted_password_b64 = await get_ontology_encrypted_password(ontology_id)
        if not encrypted_password_b64:
            logger.debug(f"Ontology {ontology_id} has no encrypted password in database")
            return None
        
        # Step 3: Decrypt the password
        encryption_key = Config.NEO4J_ENCRYPTION_KEY_BASE64
        if not encryption_key:
            logger.warning(
                f"NEO4J__ENCRYPTIONKEYBASE64 not configured. "
                f"Cannot decrypt password for ontology {ontology_id}. Falling back to default Neo4j."
            )
            return None
        
        try:
            password = decrypt_ontology_neo4j_password(encrypted_password_b64, encryption_key)
            if not password:
                logger.warning(f"Failed to decrypt password for ontology {ontology_id}")
                return None
        except Exception as e:
            logger.error(f"Password decryption failed for ontology {ontology_id}: {e}")
            return None
        
        # All three fields are present - return connection details
        logger.info(f"Successfully retrieved per-ontology Neo4j connection for ontology {ontology_id}")
        return {
            "uri": uri,
            "username": username,
            "password": password
        }
        
    except Exception as e:
        logger.error(f"Unexpected error fetching Neo4j connection for ontology {ontology_id}: {e}")
        return None
