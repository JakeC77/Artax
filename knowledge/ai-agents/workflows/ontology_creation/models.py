"""
models.py - Data models for ontology creation workflow
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class FieldDefinition(BaseModel):
    """Field definition for an entity."""
    name: str = Field(description="Field name")
    data_type: str = Field(description="Data type: string, integer, float, date, boolean, etc.")
    nullable: bool = Field(default=True, description="Whether the field can be null")
    is_identifier: bool = Field(default=False, description="True if this is an ID/identifier field")
    description: str = Field(description="Semantic description of what this field represents")


class EntityDefinition(BaseModel):
    """Entity definition in the ontology."""
    entity_id: str = Field(description="Temporary ID for references within the ontology")
    name: str = Field(description="Entity name (e.g., 'Patient', 'Claim')")
    description: str = Field(description="Semantic description of what this entity represents")
    fields: List[FieldDefinition] = Field(default_factory=list, description="Fields belonging to this entity")


class RelationshipDefinition(BaseModel):
    """Relationship definition between entities."""
    relationship_id: str = Field(description="Temporary ID for references within the ontology")
    from_entity: str = Field(description="Source entity ID")
    to_entity: str = Field(description="Target entity ID")
    relationship_type: str = Field(description="Relationship type name (e.g., 'HAS_CLAIM', 'BELONGS_TO')")
    description: str = Field(description="Semantic description of what this relationship represents")
    cardinality: Optional[str] = Field(default=None, description="Cardinality: 'one-to-one', 'one-to-many', 'many-to-many', etc.")


class IterationRecord(BaseModel):
    """A record of changes made during ontology refinement."""
    version: int = Field(description="Version number")
    timestamp: datetime = Field(default_factory=datetime.now)
    change_description: str = Field(description="What changed and why")
    user_feedback: str = Field(default="", description="User's specific feedback that prompted the change")
    semantic_version: str = Field(description="Semantic version after this change")


def increment_semantic_version(current_version: str, change_type: str) -> str:
    """
    Increment semantic version based on change type.
    
    Args:
        current_version: Current semantic version (e.g., "1.0.0")
        change_type: Type of change - "major", "minor", or "patch"
    
    Returns:
        New semantic version string
    """
    # Parse version
    parts = current_version.split(".")
    if len(parts) != 3:
        # Default to 0.1.0 if invalid
        parts = ["0", "1", "0"]
    
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except ValueError:
        major, minor, patch = 0, 1, 0
    
    # Increment based on change type
    if change_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif change_type == "minor":
        minor += 1
        patch = 0
    elif change_type == "patch":
        patch += 1
    else:
        # Default to patch increment
        patch += 1
    
    return f"{major}.{minor}.{patch}"


def validate_semantic_version(version: str) -> bool:
    """Validate semantic version format."""
    pattern = r"^\d+\.\d+\.\d+$"
    return bool(re.match(pattern, version))


class OntologyPackage(BaseModel):
    """
    The complete Ontology Package that the agent assembles
    through conversation with the user.
    """

    # Schema versioning for future migrations
    schema_version: int = Field(
        default=1,
        description="Schema version for future migrations. Increment on breaking changes."
    )

    # Ontology identification
    ontology_id: str = Field(description="UUID for resuming sessions")
    semantic_version: str = Field(
        default="0.1.0",
        description="Semantic version (MAJOR.MINOR.PATCH) for identifying ontology versions"
    )

    # User-facing summary
    title: str = Field(description="Domain name/title")
    description: str = Field(default="", description="Domain description")

    # Ontology structure
    entities: List[EntityDefinition] = Field(default_factory=list, description="Entities in the ontology")
    relationships: List[RelationshipDefinition] = Field(default_factory=list, description="Relationships between entities")

    # Conversation context
    conversation_transcript: Optional[str] = Field(
        default=None,
        description="Full conversation transcript from ontology creation for context"
    )

    # Iteration tracking
    iteration_history: List[IterationRecord] = Field(default_factory=list)
    current_version: int = Field(default=1, description="Internal version counter for tracking iterations")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    finalized: bool = Field(default=False, description="Has the user finalized this ontology?")

    @model_validator(mode='before')
    @classmethod
    def migrate_schema(cls, values):
        """
        Handle schema migrations for older OntologyPackage versions.
        """
        if isinstance(values, dict):
            version = values.get('schema_version', 1)

            # Ensure schema_version is always set
            if 'schema_version' not in values:
                values['schema_version'] = 1

            # Ensure semantic_version is set (default to 0.1.0)
            if 'semantic_version' not in values:
                values['semantic_version'] = "0.1.0"

            # Ensure updated_at is set if created_at exists
            if 'created_at' in values and 'updated_at' not in values:
                values['updated_at'] = values['created_at']

            # Log migrations for debugging
            if version != values.get('schema_version', 1):
                logger.info(f"Migrated OntologyPackage from v{version} to v{values['schema_version']}")

        return values

    def add_iteration(self, change_description: str, user_feedback: str = "", change_type: str = "patch"):
        """Record an iteration/change to the ontology and update semantic version."""
        self.current_version += 1
        self.updated_at = datetime.now()
        
        # Increment semantic version based on change type
        self.semantic_version = increment_semantic_version(self.semantic_version, change_type)
        
        self.iteration_history.append(
            IterationRecord(
                version=self.current_version,
                change_description=change_description,
                user_feedback=user_feedback,
                semantic_version=self.semantic_version
            )
        )

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "schema_version": self.schema_version,
            "ontology_id": self.ontology_id,
            "semantic_version": self.semantic_version,
            "title": self.title,
            "description": self.description,
            "entities": [
                {
                    "entity_id": e.entity_id,
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
                for e in self.entities
            ],
            "relationships": [
                {
                    "relationship_id": r.relationship_id,
                    "from_entity": r.from_entity,
                    "to_entity": r.to_entity,
                    "relationship_type": r.relationship_type,
                    "description": r.description,
                    "cardinality": r.cardinality
                }
                for r in self.relationships
            ],
            "conversation_transcript": self.conversation_transcript,
            "iteration_history": [
                {
                    "version": record.version,
                    "timestamp": record.timestamp.isoformat(),
                    "change_description": record.change_description,
                    "user_feedback": record.user_feedback,
                    "semantic_version": record.semantic_version
                }
                for record in self.iteration_history
            ],
            "current_version": self.current_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "finalized": self.finalized
        }

    def get_formatted_ontology_text(self) -> str:
        """
        Get the formatted ontology text for display.
        """
        lines = [
            f"# {self.title}",
            "",
            f"**Version:** {self.semantic_version}",
            "",
            f"{self.description}",
            "",
            "## Entities",
            ""
        ]

        for entity in self.entities:
            lines.append(f"### {entity.name}")
            lines.append(f"{entity.description}")
            lines.append("")
            if entity.fields:
                lines.append("**Fields:**")
                for field in entity.fields:
                    id_marker = " (ID)" if field.is_identifier else ""
                    nullable_marker = " (nullable)" if field.nullable else " (required)"
                    lines.append(f"- `{field.name}`: {field.data_type}{id_marker}{nullable_marker}")
                    lines.append(f"  - {field.description}")
                lines.append("")
            else:
                lines.append("*No fields defined*")
                lines.append("")

        if self.relationships:
            lines.append("## Relationships")
            lines.append("")
            for rel in self.relationships:
                from_entity = next((e.name for e in self.entities if e.entity_id == rel.from_entity), rel.from_entity)
                to_entity = next((e.name for e in self.entities if e.entity_id == rel.to_entity), rel.to_entity)
                cardinality = f" ({rel.cardinality})" if rel.cardinality else ""
                lines.append(f"- **{from_entity}** --[{rel.relationship_type}]{cardinality}--> **{to_entity}**")
                lines.append(f"  - {rel.description}")
                lines.append("")

        return "\n".join(lines)


class OntologyState:
    """
    State for ontology creation agent - tracks conversation and ontology package.
    
    Similar to TheoState, this manages the state during ontology creation conversations.
    """
    def __init__(self):
        self.ontology_package: Optional[OntologyPackage] = None
        self.ontology_proposed: bool = False  # True when agent calls propose_ontology tool
        self.ontology_finalized: bool = False  # True when user confirms
        # Broadcast signals - set by tools, consumed by ontology_builder
        self.ontology_needs_broadcast: bool = False  # True when ontology changes
        self.last_update_summary: Optional[str] = None  # Natural language summary of last update
        self.conversation_mode: bool = False  # True when used by ontology-conversation workflow

    def clear_broadcast_signal(self):
        """Clear the broadcast signal after emitting ontology_updated event."""
        self.ontology_needs_broadcast = False
        self.last_update_summary = None
