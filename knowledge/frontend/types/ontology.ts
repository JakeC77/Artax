// Ontology Creation Types
// Based on FRONTEND_GUIDE.md from ontology_creation workflow

export interface FieldDefinition {
  name: string
  data_type: string // "string", "integer", "float", "date", "boolean", etc.
  nullable: boolean
  is_identifier: boolean
  description: string
}

export interface EntityDefinition {
  entity_id: string // Temporary ID for references
  name: string
  description: string
  fields: FieldDefinition[]
}

export interface RelationshipDefinition {
  relationship_id: string // Temporary ID
  from_entity: string // Source entity ID
  to_entity: string // Target entity ID
  relationship_type: string
  description: string
  cardinality?: string // "one-to-one", "one-to-many", "many-to-many"
}

export interface IterationRecord {
  timestamp: string
  changes: string
}

export interface OntologyPackage {
  schema_version: number // Internal schema version
  ontology_id: string // UUID for resuming sessions
  semantic_version: string // "MAJOR.MINOR.PATCH" format
  title: string // Domain name/title
  description: string // Domain description
  entities: EntityDefinition[]
  relationships: RelationshipDefinition[]
  conversation_transcript?: string // Full conversation history
  iteration_history?: IterationRecord[] // Change history
  current_version: number // Internal version counter
  created_at: string // ISO datetime
  updated_at: string // ISO datetime
  finalized: boolean // Whether user confirmed
}
