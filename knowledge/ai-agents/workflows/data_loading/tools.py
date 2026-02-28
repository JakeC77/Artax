"""
tools.py - Tools for data loading agent
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic_ai import RunContext

from app.workflows.data_loading.models import (
    CSVStructure, DataMapping, EntityMapping, RelationshipMapping,
    ColumnMapping, ValidationResult, ValidationError, InsertionPreview
)
from app.workflows.data_loading.csv_parser import parse_csv_from_blob, parse_csv
from app.workflows.data_loading.graph_writer import GraphWriter
from app.workflows.ontology_creation.models import OntologyPackage

logger = logging.getLogger(__name__)

# Tool registry
DATA_LOADING_TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool."""
    def decorator(func):
        DATA_LOADING_TOOLS[name] = func
        return func
    return decorator


@register_tool("analyze_csv_structure")
async def analyze_csv_structure(
    ctx: RunContext[Dict[str, Any]],
    csv_path: Optional[str] = None,
    csv_content: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Analyze CSV file structure and return schema information.
    
    Args:
        ctx: Pydantic AI context
        csv_path: Path to CSV file in blob storage (e.g., "data-loading/{tenantId}/{runId}/input.csv")
        csv_content: CSV content as bytes (alternative to csv_path)
    
    Returns:
        Dict with CSV structure: columns, row_count, has_headers, encoding
    """
    tenant_id = ctx.deps.get("tenant_id")
    blob_service = ctx.deps.get("blob_service")
    
    if not csv_path and not csv_content:
        return {"error": "Either csv_path or csv_content must be provided"}
    
    try:
        if csv_content:
            rows, structure = parse_csv(csv_content)
        else:
            rows, structure = parse_csv_from_blob(csv_path, tenant_id, blob_service)
        
        # Store CSV rows in context for later use
        ctx.deps["csv_rows"] = rows
        ctx.deps["csv_structure"] = structure
        
        return {
            "columns": [
                {
                    "name": col.name,
                    "data_type": col.data_type,
                    "sample_values": col.sample_values[:5],  # Limit samples
                    "nullable": col.nullable
                }
                for col in structure.columns
            ],
            "row_count": structure.row_count,
            "has_headers": structure.has_headers,
            "encoding": structure.encoding
        }
    except Exception as e:
        logger.error(f"Failed to analyze CSV: {e}")
        return {"error": str(e)}


@register_tool("get_ontology")
async def get_ontology(
    ctx: RunContext[Dict[str, Any]],
    ontology_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch ontology structure for mapping CSV columns.
    
    Loads ontology from blob storage at: ontology-drafts/{tenantId}/{ontologyId}/draft.json
    in the scratchpad-attachments container.
    
    Args:
        ctx: Pydantic AI context
        ontology_id: Optional ontology ID. If not provided, uses ontology_id from workflow context
    
    Returns:
        Dict with ontology structure: entities, relationships
    """
    tenant_id = ctx.deps.get("tenant_id") or "00000000-0000-0000-0000-000000000000"
    blob_service = ctx.deps.get("blob_service")
    
    # Get ontology_id from context if not provided as parameter
    if not ontology_id:
        ontology_id = ctx.deps.get("ontology_id")
    
    # Require ontology_id - load from blob storage
    if not ontology_id:
        return {
            "error": "ontology_id is required. Please provide an ontology_id to load the ontology from blob storage."
        }
    
    try:
        import json
        from datetime import datetime
        from app.config import Config
        
        # Get blob client
        if blob_service is None:
            from azure.storage.blob import BlobServiceClient
            from azure.identity import DefaultAzureCredential
            
            conn_str = Config.AZURE_STORAGE_CONNECTION_STRING
            if conn_str:
                blob_service = BlobServiceClient.from_connection_string(conn_str)
            else:
                account_name = Config.AZURE_STORAGE_ACCOUNT_NAME
                if account_name:
                    credential = DefaultAzureCredential(
                        exclude_workload_identity_credential=True,
                        exclude_developer_cli_credential=True,
                        exclude_powershell_credential=True,
                        exclude_visual_studio_code_credential=True,
                        exclude_shared_token_cache_credential=True,
                    )
                    account_url = f"https://{account_name}.blob.core.windows.net"
                    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
                else:
                    return {"error": "Azure Storage not configured"}
        
        # Load from scratchpad-attachments container
        #TEMP
        tenant_id = "00000000-0000-0000-0000-000000000000"
        container_name = "scratchpad-attachments"
        path = f"ontology-drafts/{tenant_id}/{ontology_id}/draft.json"
        
        container = blob_service.get_container_client(container_name)
        blob = container.get_blob_client(path)
        raw = blob.download_blob().readall()
        data = json.loads(raw.decode("utf-8"))
        
        # Parse datetime strings back to datetime objects
        if isinstance(data, dict):
            if "created_at" in data and isinstance(data["created_at"], str):
                data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            if "updated_at" in data and isinstance(data["updated_at"], str):
                data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            
            # Parse iteration history timestamps
            if "iteration_history" in data:
                for record in data["iteration_history"]:
                    if "timestamp" in record and isinstance(record["timestamp"], str):
                        record["timestamp"] = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
        
        package = OntologyPackage(**data)
        logger.info(f"Loaded ontology draft from scratchpad-attachments: {path} (version {package.semantic_version})")
        
        ctx.deps["ontology_package"] = package
        return {
            "ontology_id": package.ontology_id,
            "title": package.title,
            "description": package.description,
            "entities": [
                {
                    "name": e.name,
                    "description": e.description,
                    "fields": [
                        {
                            "name": f.name,
                            "data_type": f.data_type,
                            "nullable": f.nullable,
                            "is_identifier": f.is_identifier,
                            "description": f.description
                        }
                        for f in e.fields
                    ]
                }
                for e in package.entities
            ],
            "relationships": [
                {
                    "from_entity": r.from_entity,
                    "to_entity": r.to_entity,
                    "relationship_type": r.relationship_type,
                    "description": r.description,
                    "cardinality": r.cardinality
                }
                for r in package.relationships
            ]
        }
    except Exception as e:
        logger.error(f"Failed to load ontology from blob storage: {e}")
        return {
            "error": f"Failed to load ontology from blob storage: {str(e)}. Container: scratchpad-attachments, Path: ontology-drafts/{tenant_id}/{ontology_id}/draft.json"
        }


@register_tool("map_csv_to_ontology")
async def map_csv_to_ontology(
    ctx: RunContext[Dict[str, Any]],
    entity_mappings: List[EntityMapping],
    relationship_mappings: Optional[List[RelationshipMapping]] = None
) -> Dict[str, Any]:
    """
    Store the mapping of CSV columns to ontology entities/fields.
    
    This tool is called by the agent after it has determined the mapping.
    The mapping is stored in context for validation and insertion.
    
    Args:
        ctx: Pydantic AI context
        entity_mappings: List of EntityMapping objects (validated by Pydantic)
        relationship_mappings: Optional list of RelationshipMapping objects (validated by Pydantic)
    
    Returns:
        Confirmation message
    """
    try:
        # Process entity mappings - ensure csv_columns and identifier_field are set correctly
        entity_map_objs = []
        for em in entity_mappings:
            # Ensure csv_columns is set (derive from field_mappings if missing)
            csv_cols = em.csv_columns
            if not csv_cols and em.field_mappings:
                csv_cols = [fm.csv_column for fm in em.field_mappings]
            
            # Ensure identifier_field is set (derive from field_mappings if missing)
            identifier_field = em.identifier_field
            if not identifier_field and em.field_mappings:
                identifier_field = next((fm.field_name for fm in em.field_mappings if fm.is_identifier), None)
            
            # Create a properly configured EntityMapping
            entity_map_objs.append(EntityMapping(
                entity_name=em.entity_name,
                csv_columns=csv_cols or [],
                field_mappings=em.field_mappings,
                identifier_field=identifier_field
            ))
        
        # Process relationship mappings - use them directly (already validated)
        rel_map_objs = list(relationship_mappings) if relationship_mappings else []
        
        # Get unmapped columns
        csv_structure: CSVStructure = ctx.deps.get("csv_structure")
        mapped_columns = set()
        for em in entity_map_objs:
            mapped_columns.update(em.csv_columns)
        for rm in rel_map_objs:
            mapped_columns.update(rm.csv_columns)
        
        unmapped = [
            col.name for col in csv_structure.columns
            if col.name not in mapped_columns
        ]
        
        mapping = DataMapping(
            entity_mappings=entity_map_objs,
            relationship_mappings=rel_map_objs,
            unmapped_columns=unmapped
        )
        
        ctx.deps["mapping"] = mapping
        
        return {
            "success": True,
            "message": f"Mapped {len(entity_map_objs)} entities and {len(rel_map_objs)} relationships",
            "unmapped_columns": unmapped
        }
    except Exception as e:
        logger.error(f"Failed to store mapping: {e}")
        return {"error": str(e)}


@register_tool("validate_mapping")
async def validate_mapping(
    ctx: RunContext[Dict[str, Any]],
    sample_rows: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Validate the CSV-to-ontology mapping against sample data.
    
    Args:
        ctx: Pydantic AI context
        sample_rows: Number of rows to sample for validation
    
    Returns:
        Validation results with errors and warnings
    """
    mapping: DataMapping = ctx.deps.get("mapping")
    csv_rows: List[Dict[str, str]] = ctx.deps.get("csv_rows", [])
    csv_structure: CSVStructure = ctx.deps.get("csv_structure")
    
    if not mapping:
        return {"error": "No mapping found. Call map_csv_to_ontology first."}
    
    if not csv_rows:
        return {"error": "No CSV rows found. Call analyze_csv_structure first."}
    
    errors = []
    warnings = []
    
    # Sample rows for validation
    sample = csv_rows[:min(sample_rows, len(csv_rows))]
    
    # Validate entity mappings
    for em in mapping.entity_mappings:
        identifier_field = em.identifier_field
        if not identifier_field:
            warnings.append(ValidationError(
                error_type="missing_field",
                message=f"Entity {em.entity_name} has no identifier field",
                column_name=None
            ))
        
        # Check for duplicate identifiers
        identifiers = {}
        for i, row in enumerate(sample):
            id_value = row.get(identifier_field) if identifier_field else None
            if id_value:
                if id_value in identifiers:
                    errors.append(ValidationError(
                        error_type="duplicate_identifier",
                        message=f"Duplicate identifier '{id_value}' for entity {em.entity_name}",
                        row_number=i + 1,
                        column_name=identifier_field
                    ))
                identifiers[id_value] = i
        
        # Validate field types
        for fm in em.field_mappings:
            csv_col = fm.csv_column
            if csv_col not in [c.name for c in csv_structure.columns]:
                errors.append(ValidationError(
                    error_type="missing_field",
                    message=f"CSV column '{csv_col}' not found",
                    column_name=csv_col
                ))
                continue
            
            # Check type compatibility
            csv_col_obj = next(c for c in csv_structure.columns if c.name == csv_col)
            if csv_col_obj.data_type != fm.data_type:
                # Allow some flexibility (e.g., integer -> float)
                if not (csv_col_obj.data_type == "integer" and fm.data_type == "float"):
                    warnings.append(ValidationError(
                        error_type="type_mismatch",
                        message=f"Type mismatch: CSV column '{csv_col}' is {csv_col_obj.data_type}, but field '{fm.field_name}' expects {fm.data_type}",
                        column_name=csv_col
                    ))
    
    # Validate relationship mappings
    for rm in mapping.relationship_mappings:
        # Check that required columns exist
        for col in rm.csv_columns:
            if col not in [c.name for c in csv_structure.columns]:
                errors.append(ValidationError(
                    error_type="missing_field",
                    message=f"CSV column '{col}' not found for relationship {rm.relationship_type}",
                    column_name=col
                ))
    
    is_valid = len(errors) == 0
    
    result = ValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        summary=f"Validation {'passed' if is_valid else 'failed'}: {len(errors)} errors, {len(warnings)} warnings"
    )
    
    ctx.deps["validation_result"] = result
    
    return {
        "is_valid": is_valid,
        "errors": [{"type": e.error_type, "message": e.message, "row": e.row_number, "column": e.column_name} for e in errors],
        "warnings": [{"type": w.error_type, "message": w.message, "row": w.row_number, "column": w.column_name} for w in warnings],
        "summary": result.summary
    }


@register_tool("preview_insertion")
async def preview_insertion(
    ctx: RunContext[Dict[str, Any]],
    preview_rows: Optional[int] = 5
) -> Dict[str, Any]:
    """
    Preview what will be inserted into the graph (dry-run).
    
    Args:
        ctx: Pydantic AI context
        preview_rows: Number of rows to preview
    
    Returns:
        Preview of nodes and relationships to be created
    """
    mapping: DataMapping = ctx.deps.get("mapping")
    csv_rows: List[Dict[str, str]] = ctx.deps.get("csv_rows", [])
    
    if not mapping:
        return {"error": "No mapping found. Call map_csv_to_ontology first."}
    
    if not csv_rows:
        return {"error": "No CSV rows found. Call analyze_csv_structure first."}
    
    # Sample rows
    sample = csv_rows[:min(preview_rows, len(csv_rows))]
    
    # Build preview
    nodes_to_create = {}
    sample_nodes = {}
    sample_relationships = []
    
    # Process entity mappings
    for em in mapping.entity_mappings:
        entity_name = em.entity_name
        nodes_to_create[entity_name] = len(csv_rows)  # Total count
        
        # Build sample nodes
        sample_nodes[entity_name] = []
        for row in sample:
            node_props = {}
            for fm in em.field_mappings:
                csv_value = row.get(fm.csv_column)
                if csv_value:
                    node_props[fm.field_name] = csv_value
            sample_nodes[entity_name].append(node_props)
    
    # Process relationship mappings
    relationships_to_create = {}
    for rm in mapping.relationship_mappings:
        rel_type = rm.relationship_type
        relationships_to_create[rel_type] = len(csv_rows)  # Approximate
        
        # Build sample relationships
        for row in sample:
            from_id = row.get(rm.from_identifier_field)
            to_id = row.get(rm.to_identifier_field)
            if from_id and to_id:
                sample_relationships.append({
                    "from": from_id,
                    "to": to_id,
                    "type": rel_type,
                    "properties": {k: row.get(v) for k, v in rm.properties.items()}
                })
    
    preview = InsertionPreview(
        nodes_to_create=nodes_to_create,
        relationships_to_create=relationships_to_create,
        sample_nodes=sample_nodes,
        sample_relationships=sample_relationships[:preview_rows]
    )
    
    ctx.deps["preview"] = preview
    
    return {
        "nodes_to_create": nodes_to_create,
        "relationships_to_create": relationships_to_create,
        "sample_nodes": {k: v[:3] for k, v in sample_nodes.items()},  # Limit samples
        "sample_relationships": sample_relationships[:preview_rows],
        "total_rows": len(csv_rows)
    }


@register_tool("create_graph_nodes")
async def create_graph_nodes(
    ctx: RunContext[Dict[str, Any]],
    entity_name: str,
    batch_size: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create nodes in the graph for a specific entity type.
    
    Args:
        ctx: Pydantic AI context
        entity_name: Entity name to create nodes for
        batch_size: Batch size for insertion (defaults to config)
    
    Returns:
        Results with created node IDs and errors
    """
    mapping: DataMapping = ctx.deps.get("mapping")
    csv_rows: List[Dict[str, str]] = ctx.deps.get("csv_rows", [])
    workspace_id = ctx.deps.get("workspace_id")
    tenant_id = ctx.deps.get("tenant_id")
    
    if not mapping or not csv_rows:
        return {"error": "Missing mapping or CSV rows"}
    
    # Find entity mapping
    em = next((e for e in mapping.entity_mappings if e.entity_name == entity_name), None)
    if not em:
        return {"error": f"Entity mapping not found for {entity_name}"}
    
    # Get batch size from config or context
    if batch_size is None:
        from app.workflows.data_loading.config import load_config
        config = load_config()
        batch_size = config.max_batch_size
    
    # Create graph writer with per-ontology connection if available
    neo4j_connection = ctx.deps.get("neo4j_connection")
    if neo4j_connection:
        writer = GraphWriter(
            workspace_id,
            tenant_id,
            neo4j_uri=neo4j_connection.get("uri"),
            neo4j_username=neo4j_connection.get("username"),
            neo4j_password=neo4j_connection.get("password")
        )
    else:
        writer = GraphWriter(workspace_id, tenant_id)
    
    # Build nodes
    nodes = []
    for row in csv_rows:
        properties = {}
        for fm in em.field_mappings:
            csv_value = row.get(fm.csv_column)
            if csv_value:
                properties[fm.field_name] = csv_value
        
        if properties:  # Only add if has properties
            nodes.append({
                "labels": [entity_name],
                "properties": properties
            })
    
    # Create nodes in batches
    created_count = 0
    errors = []
    
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i + batch_size]
        results = await writer.batch_create_nodes(batch)
        
        for result in results:
            if result.get("success"):
                created_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))
    
    # Update state
    state = ctx.deps.get("state")
    if state:
        state.nodes_created += created_count
    
    return {
        "entity_name": entity_name,
        "created": created_count,
        "total": len(nodes),
        "errors": errors[:10]  # Limit error messages
    }


@register_tool("create_graph_relationships")
async def create_graph_relationships(
    ctx: RunContext[Dict[str, Any]],
    relationship_type: Optional[str] = None,
    batch_size: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create relationships in the graph.
    
    Args:
        ctx: Pydantic AI context
        relationship_type: Optional specific relationship type (if None, creates all)
        batch_size: Batch size for insertion (defaults to config)
    
    Returns:
        Results with created relationship IDs and errors
    """
    mapping: DataMapping = ctx.deps.get("mapping")
    csv_rows: List[Dict[str, str]] = ctx.deps.get("csv_rows", [])
    workspace_id = ctx.deps.get("workspace_id")
    tenant_id = ctx.deps.get("tenant_id")
    
    if not mapping or not csv_rows:
        return {"error": "Missing mapping or CSV rows"}
    
    # Get batch size from config
    if batch_size is None:
        from app.workflows.data_loading.config import load_config
        config = load_config()
        batch_size = config.max_batch_size
    
    # Create graph writer with per-ontology connection if available
    neo4j_connection = ctx.deps.get("neo4j_connection")
    if neo4j_connection:
        writer = GraphWriter(
            workspace_id,
            tenant_id,
            neo4j_uri=neo4j_connection.get("uri"),
            neo4j_username=neo4j_connection.get("username"),
            neo4j_password=neo4j_connection.get("password")
        )
    else:
        writer = GraphWriter(workspace_id, tenant_id)
    
    # Filter relationship mappings
    rel_mappings = mapping.relationship_mappings
    if relationship_type:
        rel_mappings = [rm for rm in rel_mappings if rm.relationship_type == relationship_type]
    
    # Build relationships
    relationships = []
    for rm in rel_mappings:
        # Find entity mappings to get CSV column names for identifier fields
        from_em = next((em for em in mapping.entity_mappings if em.entity_name == rm.from_entity), None)
        to_em = next((em for em in mapping.entity_mappings if em.entity_name == rm.to_entity), None)
        
        if not from_em or not to_em:
            continue  # Skip if entity mappings not found
        
        # Find CSV column names for identifier fields
        from_csv_col = None
        for fm in from_em.field_mappings:
            if fm.field_name == rm.from_identifier_field:
                from_csv_col = fm.csv_column
                break
        
        to_csv_col = None
        for fm in to_em.field_mappings:
            if fm.field_name == rm.to_identifier_field:
                to_csv_col = fm.csv_column
                break
        
        if not from_csv_col or not to_csv_col:
            continue  # Skip if CSV columns not found
        
        for row in csv_rows:
            from_id = row.get(from_csv_col)
            to_id = row.get(to_csv_col)
            
            if from_id and to_id:
                props = {k: row.get(v) for k, v in rm.properties.items() if row.get(v)}
                relationships.append({
                    "fromId": from_id,
                    "toId": to_id,
                    "type": rm.relationship_type,
                    "fromIdentifierField": rm.from_identifier_field,
                    "toIdentifierField": rm.to_identifier_field,
                    "properties": props
                })
    
    # Create relationships in batches
    created_count = 0
    errors = []
    
    for i in range(0, len(relationships), batch_size):
        batch = relationships[i:i + batch_size]
        results = await writer.batch_create_relationships(batch)
        
        for result in results:
            if result.get("success"):
                created_count += 1
            else:
                errors.append(result.get("error", "Unknown error"))
    
    # Update state
    state = ctx.deps.get("state")
    if state:
        state.relationships_created += created_count
    
    return {
        "created": created_count,
        "total": len(relationships),
        "errors": errors[:10]  # Limit error messages
    }
