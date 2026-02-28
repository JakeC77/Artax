"""
graph_writer.py - Interface for writing nodes and relationships to graph database using Cypher
"""

import logging
from typing import List, Dict, Any, Optional
from app.config import Config

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncGraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None


def _is_neo4j_configured(uri: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None) -> bool:
    """Return True if Neo4j is configured and available."""
    if not _NEO4J_AVAILABLE:
        return False
    
    # Use provided connection details or fall back to config
    check_uri = uri or Config.NEO4J_URI
    check_username = username or Config.NEO4J_USER
    check_password = password or Config.NEO4J_PASSWORD
    
    if not check_uri or not check_username:
        return False
    if not check_password:
        logger.warning("Neo4j enabled but password is empty")
        return False
    return True


def _escape_cypher_string(value: Any) -> str:
    """Escape a value for use in Cypher queries."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # Escape quotes and backslashes
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    # For other types, convert to string
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _properties_to_cypher(properties: Dict[str, Any]) -> str:
    """Convert properties dict to Cypher property string."""
    if not properties:
        return ""
    props = []
    for key, value in properties.items():
        # Escape key (should be valid identifier, but be safe)
        safe_key = key.replace("`", "``")
        props.append(f"`{safe_key}`: {_escape_cypher_string(value)}")
    return ", ".join(props)


class GraphWriter:
    """Interface for writing nodes and relationships to graph database using Cypher."""
    
    def __init__(
        self,
        workspace_id: str,
        tenant_id: str,
        neo4j_uri: Optional[str] = None,
        neo4j_username: Optional[str] = None,
        neo4j_password: Optional[str] = None
    ):
        """
        Initialize graph writer.
        
        Args:
            workspace_id: Workspace UUID (for logging/context)
            tenant_id: Tenant ID (for logging/context)
            neo4j_uri: Optional Neo4j URI (uses Config.NEO4J_URI if not provided)
            neo4j_username: Optional Neo4j username (uses Config.NEO4J_USER if not provided)
            neo4j_password: Optional Neo4j password (uses Config.NEO4J_PASSWORD if not provided)
        """
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.neo4j_uri = neo4j_uri
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        self._driver: Optional[Any] = None
    
    async def _get_or_create_driver(self):
        """Get or create Neo4j driver for this instance. Returns None if not configured."""
        if self._driver is not None:
            return self._driver
        
        # Use instance connection details or fall back to config
        uri = self.neo4j_uri or Config.NEO4J_URI
        username = self.neo4j_username or Config.NEO4J_USER
        password = self.neo4j_password or Config.NEO4J_PASSWORD
        
        if not _is_neo4j_configured(uri, username, password):
            return None
        
        try:
            self._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(username, password),
            )
            await self._driver.verify_connectivity()
            logger.info(f"Neo4j driver initialized successfully (workspace: {self.workspace_id})")
            return self._driver
        except Exception as e:
            logger.warning(f"Failed to create Neo4j driver: {e}")
            return None
    
    async def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any]
    ) -> Optional[str]:
        """
        Create a single node in the graph.
        
        Args:
            labels: Node labels (entity types)
            properties: Node properties
        
        Returns:
            Created node ID (from id property or internal ID), or None if failed
        """
        try:
            driver = await self._get_or_create_driver()
            if not driver:
                logger.error("Neo4j driver not available")
                return None
            
            # Build Cypher query
            labels_str = ":".join(labels)
            props_str = _properties_to_cypher(properties)
            
            cypher = f"CREATE (n:{labels_str} {{{props_str}}}) RETURN id(n) as nodeId, n.id as nodeIdProp"
            
            async def _write(tx: Any) -> Optional[str]:
                result = await tx.run(cypher)
                record = await result.single()
                if record:
                    # Prefer id property, fallback to internal ID
                    node_id = record.get("nodeIdProp") or str(record.get("nodeId"))
                    return node_id
                return None
            
            async with driver.session() as session:
                node_id = await session.execute_write(_write)
            
            if node_id:
                logger.debug(f"Created node: {node_id} with labels {labels}")
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to create node: {e}")
            return None
    
    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create a relationship between two nodes.
        
        Args:
            from_id: Source node ID (property id or internal ID)
            to_id: Target node ID (property id or internal ID)
            relationship_type: Relationship type name
            properties: Optional relationship properties
        
        Returns:
            Created relationship ID, or None if failed
        """
        try:
            driver = await self._get_or_create_driver()
            if not driver:
                logger.error("Neo4j driver not available")
                return None
            
            # Build Cypher query
            # Try to match by id property first, fallback to internal ID
            props_str = _properties_to_cypher(properties or {})
            rel_props = f" {{{props_str}}}" if props_str else ""
            
            cypher = f"""
            MATCH (from) WHERE from.id = {_escape_cypher_string(from_id)} OR id(from) = {_escape_cypher_string(from_id)}
            MATCH (to) WHERE to.id = {_escape_cypher_string(to_id)} OR id(to) = {_escape_cypher_string(to_id)}
            CREATE (from)-[r:{relationship_type}{rel_props}]->(to)
            RETURN id(r) as relId
            """
            
            async def _write(tx: Any) -> Optional[str]:
                result = await tx.run(cypher)
                record = await result.single()
                if record:
                    return str(record.get("relId"))
                return None
            
            async with driver.session() as session:
                rel_id = await session.execute_write(_write)
            
            if rel_id:
                logger.debug(f"Created relationship: {rel_id} ({relationship_type})")
            return rel_id
            
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return None
    
    async def batch_create_nodes(
        self,
        nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create multiple nodes in a batch using Cypher UNWIND.
        
        Args:
            nodes: List of node dicts with 'labels' and 'properties' keys
        
        Returns:
            List of results with 'nodeId', 'success', 'error' keys
        """
        if not nodes:
            return []
        
        try:
            driver = await self._get_or_create_driver()
            if not driver:
                logger.error("Neo4j driver not available")
                return [{"nodeId": None, "success": False, "error": "Neo4j driver not available"} for _ in nodes]
            
            async def _write(tx: Any) -> List[Dict[str, Any]]:
                results = []
                
                # Group nodes by labels for batch efficiency (same labels can use UNWIND)
                nodes_by_label = {}
                for i, node in enumerate(nodes):
                    labels_key = ":".join(sorted(node["labels"]))
                    if labels_key not in nodes_by_label:
                        nodes_by_label[labels_key] = []
                    nodes_by_label[labels_key].append((i, node))
                
                # Process each label group
                for labels_key, node_list in nodes_by_label.items():
                    labels = node_list[0][1]["labels"]
                    labels_str = ":".join(labels)
                    
                    # Prepare nodes data for UNWIND (using parameters)
                    nodes_params = []
                    for idx, node in node_list:
                        nodes_params.append(node["properties"])
                    
                    # Use UNWIND for batch creation
                    cypher = f"""
                    UNWIND $nodes AS props
                    CREATE (n:{labels_str})
                    SET n = props
                    RETURN id(n) as nodeId, n.id as nodeIdProp
                    """
                    
                    try:
                        result = await tx.run(cypher, {"nodes": nodes_params})
                        records = await result.data()
                        
                        # Map results back to original order
                        for idx, (original_idx, _) in enumerate(node_list):
                            if idx < len(records):
                                record = records[idx]
                                node_id = record.get("nodeIdProp") or str(record.get("nodeId"))
                                results.append({
                                    "nodeId": node_id,
                                    "success": True,
                                    "error": None
                                })
                            else:
                                results.append({
                                    "nodeId": None,
                                    "success": False,
                                    "error": "No record returned"
                                })
                    except Exception as e:
                        logger.error(f"Failed to create nodes in batch for {labels_str}: {e}")
                        # Fallback to individual creates for this label group
                        for idx, node in node_list:
                            try:
                                props_str = _properties_to_cypher(node["properties"])
                                single_cypher = f"CREATE (n:{labels_str} {{{props_str}}}) RETURN id(n) as nodeId, n.id as nodeIdProp"
                                single_result = await tx.run(single_cypher)
                                record = await single_result.single()
                                if record:
                                    node_id = record.get("nodeIdProp") or str(record.get("nodeId"))
                                    results.append({
                                        "nodeId": node_id,
                                        "success": True,
                                        "error": None
                                    })
                                else:
                                    results.append({
                                        "nodeId": None,
                                        "success": False,
                                        "error": "No record returned"
                                    })
                            except Exception as single_e:
                                logger.error(f"Failed to create individual node: {single_e}")
                                results.append({
                                    "nodeId": None,
                                    "success": False,
                                    "error": str(single_e)
                                })
                
                return results
            
            async with driver.session() as session:
                results = await session.execute_write(_write)
            
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"Batch created {success_count}/{len(nodes)} nodes")
            return results
            
        except Exception as e:
            logger.error(f"Failed to batch create nodes: {e}")
            # Fallback to individual creates
            logger.info("Falling back to individual node creation")
            results = []
            for node in nodes:
                node_id = await self.create_node(node["labels"], node["properties"])
                results.append({
                    "nodeId": node_id,
                    "success": node_id is not None,
                    "error": None if node_id else "Failed to create node"
                })
            return results
    
    async def batch_create_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create multiple relationships in a batch using Cypher UNWIND.
        
        Args:
            relationships: List of relationship dicts with 'fromId', 'toId', 'type', 'properties' keys
        
        Returns:
            List of results with 'relationshipId', 'success', 'error' keys
        """
        if not relationships:
            return []
        
        try:
            driver = await self._get_or_create_driver()
            if not driver:
                logger.error("Neo4j driver not available")
                return [{"relationshipId": None, "success": False, "error": "Neo4j driver not available"} for _ in relationships]
            
            async def _write(tx: Any) -> List[Dict[str, Any]]:
                results = []
                
                # Group relationships by type for batch efficiency
                rels_by_type = {}
                for i, rel in enumerate(relationships):
                    rel_type = rel["type"]
                    if rel_type not in rels_by_type:
                        rels_by_type[rel_type] = []
                    rels_by_type[rel_type].append((i, rel))
                
                # Process each relationship type group
                for rel_type, rel_list in rels_by_type.items():
                    for idx, rel in rel_list:
                        from_id = rel["fromId"]
                        to_id = rel["toId"]
                        props = rel.get("properties", {})
                        props_str = _properties_to_cypher(props)
                        rel_props = f" {{{props_str}}}" if props_str else ""
                        
                        # Get identifier field names (default to "id" if not provided for backward compatibility)
                        from_field = rel.get("fromIdentifierField", "id")
                        to_field = rel.get("toIdentifierField", "id")
                        
                        # Escape field names for Cypher (handle backticks)
                        from_field_escaped = from_field.replace("`", "``")
                        to_field_escaped = to_field.replace("`", "``")
                        
                        cypher = f"""
                        MATCH (from) WHERE from.`{from_field_escaped}` = {_escape_cypher_string(from_id)}
                        MATCH (to) WHERE to.`{to_field_escaped}` = {_escape_cypher_string(to_id)}
                        CREATE (from)-[r:{rel_type}{rel_props}]->(to)
                        RETURN id(r) as relId
                        """
                        
                        try:
                            result = await tx.run(cypher)
                            record = await result.single()
                            if record:
                                rel_id = str(record.get("relId"))
                                results.append({
                                    "relationshipId": rel_id,
                                    "success": True,
                                    "error": None
                                })
                            else:
                                results.append({
                                    "relationshipId": None,
                                    "success": False,
                                    "error": "No record returned"
                                })
                        except Exception as e:
                            logger.error(f"Failed to create relationship in batch: {e}")
                            results.append({
                                "relationshipId": None,
                                "success": False,
                                "error": str(e)
                            })
                
                return results
            
            async with driver.session() as session:
                results = await session.execute_write(_write)
            
            success_count = sum(1 for r in results if r.get("success"))
            logger.info(f"Batch created {success_count}/{len(relationships)} relationships")
            return results
            
        except Exception as e:
            logger.error(f"Failed to batch create relationships: {e}")
            # Fallback to individual creates
            logger.info("Falling back to individual relationship creation")
            results = []
            for rel in relationships:
                rel_id = await self.create_relationship(
                    rel["fromId"],
                    rel["toId"],
                    rel["type"],
                    rel.get("properties")
                )
                results.append({
                    "relationshipId": rel_id,
                    "success": rel_id is not None,
                    "error": None if rel_id else "Failed to create relationship"
                })
            return results
