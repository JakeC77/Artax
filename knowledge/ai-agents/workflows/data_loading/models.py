"""
models.py - Data models for data loading workflow
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class CSVColumn(BaseModel):
    """Represents a column in the CSV file."""
    name: str = Field(description="Column name")
    data_type: str = Field(description="Inferred data type: string, integer, float, date, boolean")
    sample_values: List[str] = Field(default_factory=list, description="Sample values from the CSV")
    nullable: bool = Field(default=True, description="Whether column contains null/empty values")


class CSVStructure(BaseModel):
    """CSV schema representation."""
    columns: List[CSVColumn] = Field(default_factory=list, description="Columns in the CSV")
    row_count: int = Field(description="Total number of data rows")
    has_headers: bool = Field(default=True, description="Whether CSV has header row")
    encoding: str = Field(default="utf-8", description="File encoding detected")


class ColumnMapping(BaseModel):
    """Maps a CSV column to an ontology field."""
    csv_column: str = Field(description="CSV column name")
    field_name: str = Field(description="Ontology field name")
    entity_name: str = Field(description="Entity this field belongs to")
    is_identifier: bool = Field(default=False, description="Whether this field is an identifier")
    data_type: str = Field(description="Expected data type")
    nullable: bool = Field(default=True, description="Whether field can be null")


class EntityMapping(BaseModel):
    """Maps CSV rows to an entity type."""
    entity_name: str = Field(description="Entity name from ontology")
    csv_columns: List[str] = Field(description="CSV columns used for this entity")
    field_mappings: List[ColumnMapping] = Field(default_factory=list, description="Field mappings")
    identifier_field: Optional[str] = Field(default=None, description="Field used as identifier")


class RelationshipMapping(BaseModel):
    """Maps CSV data to a relationship."""
    relationship_type: str = Field(description="Relationship type name")
    from_entity: str = Field(description="Source entity name")
    to_entity: str = Field(description="Target entity name")
    csv_columns: List[str] = Field(description="CSV columns used to create relationship")
    from_identifier_field: str = Field(description="Field in from_entity used to match")
    to_identifier_field: str = Field(description="Field in to_entity used to match")
    properties: Dict[str, str] = Field(default_factory=dict, description="Additional properties from CSV columns")


class DataMapping(BaseModel):
    """Complete mapping of CSV to ontology."""
    entity_mappings: List[EntityMapping] = Field(default_factory=list, description="Entity mappings")
    relationship_mappings: List[RelationshipMapping] = Field(default_factory=list, description="Relationship mappings")
    unmapped_columns: List[str] = Field(default_factory=list, description="CSV columns not mapped to ontology")


class ValidationError(BaseModel):
    """A validation error found in the mapping or data."""
    error_type: str = Field(description="Type of error: type_mismatch, missing_field, invalid_identifier, duplicate_identifier")
    message: str = Field(description="Error message")
    row_number: Optional[int] = Field(default=None, description="Row number where error occurred (if applicable)")
    column_name: Optional[str] = Field(default=None, description="Column name where error occurred (if applicable)")


class ValidationResult(BaseModel):
    """Results of mapping validation."""
    is_valid: bool = Field(description="Whether mapping is valid")
    errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")
    warnings: List[ValidationError] = Field(default_factory=list, description="Validation warnings")
    summary: str = Field(description="Summary of validation results")


class InsertionPreview(BaseModel):
    """Preview of what will be inserted."""
    nodes_to_create: Dict[str, int] = Field(description="Entity name -> count of nodes to create")
    relationships_to_create: Dict[str, int] = Field(description="Relationship type -> count of relationships to create")
    sample_nodes: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Sample nodes by entity type")
    sample_relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Sample relationships")


class DataLoadingState(BaseModel):
    """Tracks the state of data loading process."""
    csv_structure: Optional[CSVStructure] = None
    ontology_id: Optional[str] = None
    mapping: Optional[DataMapping] = None
    validation_result: Optional[ValidationResult] = None
    preview: Optional[InsertionPreview] = None
    nodes_created: int = 0
    relationships_created: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
