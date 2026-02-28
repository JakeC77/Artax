/**
 * Mock data for testing DataScopingView components
 *
 * Usage: Import and use in development/testing environments
 * to test UI without running actual AI workflows.
 */

import type { ScopeState, ScopeEntity, Filter, Relationship, FieldOfInterest } from '../../../../../types/scopeState'
import type { IntentPackage } from '../../../../../services/graphql'

// ============================================================================
// Mock Filters
// ============================================================================

const mockFilters: Record<string, Filter[]> = {
  Plan: [
    {
      id: 'filter-1',
      property: 'state',
      operator: 'in',
      value: ['CA', 'TX', 'NY', 'FL'],
      display_text: 'State in CA, TX, NY, FL',
      reasoning: 'Focusing on high-population states with significant market presence',
    },
    {
      id: 'filter-2',
      property: 'plan_type',
      operator: 'equals',
      value: 'PPO',
      display_text: 'Plan type = PPO',
      reasoning: 'PPO plans represent the largest segment of the market',
    },
    {
      id: 'filter-3',
      property: 'effective_date',
      operator: 'between',
      value: ['2024-01-01', '2024-12-31'],
      display_text: 'Effective date between Jan 1, 2024 and Dec 31, 2024',
      reasoning: 'Analyzing current year plans only',
    },
  ],
  Member: [
    {
      id: 'filter-4',
      property: 'age',
      operator: 'between',
      value: [18, 65],
      display_text: 'Age between 18 and 65',
      reasoning: 'Working age population analysis',
    },
    {
      id: 'filter-5',
      property: 'enrollment_status',
      operator: 'equals',
      value: 'active',
      display_text: 'Enrollment status = Active',
      reasoning: 'Only including currently enrolled members',
    },
  ],
  Claim: [
    {
      id: 'filter-6',
      property: 'claim_date',
      operator: 'greater_than',
      value: '2024-01-01',
      display_text: 'Claim date after Jan 1, 2024',
      reasoning: 'Recent claims for current year analysis',
    },
    {
      id: 'filter-7',
      property: 'claim_amount',
      operator: 'greater_than',
      value: 1000,
      display_text: 'Claim amount > $1,000',
      reasoning: 'Focusing on significant claims',
    },
  ],
  Provider: [
    {
      id: 'filter-8',
      property: 'specialty',
      operator: 'in',
      value: ['Primary Care', 'Cardiology', 'Orthopedics'],
      display_text: 'Specialty in Primary Care, Cardiology, Orthopedics',
      reasoning: 'High-volume specialties for cost analysis',
    },
  ],
  Drug: [],
}

// ============================================================================
// Mock Fields of Interest
// ============================================================================

const mockFieldsOfInterest: Record<string, FieldOfInterest[]> = {
  Plan: [
    { field: 'plan_id', justification: 'Primary identifier for joining data' },
    { field: 'plan_name', justification: 'Human-readable plan identification' },
    { field: 'plan_type', justification: 'Key segmentation dimension' },
    { field: 'state', justification: 'Geographic analysis requirement' },
    { field: 'premium', justification: 'Core financial metric' },
    { field: 'deductible', justification: 'Member cost-sharing analysis' },
  ],
  Member: [
    { field: 'member_id', justification: 'Primary identifier' },
    { field: 'age', justification: 'Demographic segmentation' },
    { field: 'gender', justification: 'Demographic analysis' },
    { field: 'enrollment_date', justification: 'Tenure analysis' },
    { field: 'plan_id', justification: 'Plan association' },
  ],
  Claim: [
    { field: 'claim_id', justification: 'Primary identifier' },
    { field: 'member_id', justification: 'Member association' },
    { field: 'provider_id', justification: 'Provider association' },
    { field: 'claim_amount', justification: 'Cost analysis' },
    { field: 'service_date', justification: 'Temporal analysis' },
    { field: 'diagnosis_code', justification: 'Clinical categorization' },
  ],
  Provider: [
    { field: 'provider_id', justification: 'Primary identifier' },
    { field: 'provider_name', justification: 'Display purposes' },
    { field: 'specialty', justification: 'Provider segmentation' },
    { field: 'network_status', justification: 'Network analysis' },
  ],
  Drug: [
    { field: 'ndc', justification: 'Drug identifier' },
    { field: 'drug_name', justification: 'Display purposes' },
    { field: 'therapeutic_class', justification: 'Drug categorization' },
    { field: 'generic_available', justification: 'Cost optimization analysis' },
  ],
}

// ============================================================================
// Mock Entities
// ============================================================================

// ============================================================================
// Mock Cypher Queries
// ============================================================================

const mockQueries: Record<string, string> = {
  Plan: `MATCH (n:\`Plan\`) RETURN n`,
  Member: `MATCH (n:\`Member\`) RETURN n`,
  Claim: `MATCH (n:\`Claim\`) RETURN n`,
  Provider: `MATCH (n:\`Provider\`) RETURN n`,
  Drug: `MATCH (n:\`Drug\`) RETURN n`,
  Prescription: `MATCH (n:\`Prescription\`) RETURN n`,
  Diagnosis: `MATCH (n:\`Diagnosis\`) RETURN n`,
}

export const mockEntities: ScopeEntity[] = [
  {
    entity_type: 'Plan',
    relevance_level: 'primary',
    reasoning: 'Plans are the central entity for this analysis. Understanding plan characteristics, enrollment, and costs is the primary objective.',
    enabled: true,
    filters: mockFilters.Plan,
    fields_of_interest: mockFieldsOfInterest.Plan,
    estimated_count: 1247,
    query: mockQueries.Plan,
  },
  {
    entity_type: 'Member',
    relevance_level: 'related',
    reasoning: 'Members are enrolled in plans and generate claims. Member demographics drive plan utilization patterns.',
    enabled: true,
    filters: mockFilters.Member,
    fields_of_interest: mockFieldsOfInterest.Member,
    estimated_count: 125430,
    query: mockQueries.Member,
  },
  {
    entity_type: 'Claim',
    relevance_level: 'related',
    reasoning: 'Claims represent the financial transactions and utilization patterns that determine plan costs.',
    enabled: true,
    filters: mockFilters.Claim,
    fields_of_interest: mockFieldsOfInterest.Claim,
    estimated_count: 2847291,
    query: mockQueries.Claim,
  },
  {
    entity_type: 'Provider',
    relevance_level: 'contextual',
    reasoning: 'Providers deliver services and influence costs through practice patterns and network participation.',
    enabled: true,
    filters: mockFilters.Provider,
    fields_of_interest: mockFieldsOfInterest.Provider,
    estimated_count: 8923,
    query: mockQueries.Provider,
  },
  {
    entity_type: 'Drug',
    relevance_level: 'contextual',
    reasoning: 'Pharmacy costs are a significant component of overall plan costs.',
    enabled: false, // Disabled by default to show toggle functionality
    filters: mockFilters.Drug,
    fields_of_interest: mockFieldsOfInterest.Drug,
    estimated_count: 15420,
    query: mockQueries.Drug,
  },
]

// ============================================================================
// Mock Relationships
// ============================================================================

export const mockRelationships: Relationship[] = [
  {
    from_entity: 'Plan',
    to_entity: 'Member',
    relationship_type: 'HAS_ENROLLED',
    display_label: 'enrolls',
  },
  {
    from_entity: 'Member',
    to_entity: 'Claim',
    relationship_type: 'SUBMITS',
    display_label: 'submits',
  },
  {
    from_entity: 'Claim',
    to_entity: 'Provider',
    relationship_type: 'SERVICED_BY',
    display_label: 'serviced by',
  },
  {
    from_entity: 'Claim',
    to_entity: 'Drug',
    relationship_type: 'INCLUDES',
    display_label: 'includes',
  },
  {
    from_entity: 'Provider',
    to_entity: 'Plan',
    relationship_type: 'IN_NETWORK',
    display_label: 'in network',
  },
]

// ============================================================================
// Mock Sample Data
// ============================================================================

export const mockSamples: Record<string, Record<string, unknown>[]> = {
  Plan: [
    { plan_id: 'PLN-001', plan_name: 'Blue Shield PPO Gold', plan_type: 'PPO', state: 'CA', premium: 850, deductible: 1500 },
    { plan_id: 'PLN-002', plan_name: 'Aetna PPO Silver', plan_type: 'PPO', state: 'TX', premium: 720, deductible: 2500 },
    { plan_id: 'PLN-003', plan_name: 'United PPO Bronze', plan_type: 'PPO', state: 'NY', premium: 550, deductible: 4000 },
    { plan_id: 'PLN-004', plan_name: 'Cigna PPO Platinum', plan_type: 'PPO', state: 'FL', premium: 1100, deductible: 500 },
    { plan_id: 'PLN-005', plan_name: 'Humana PPO Gold', plan_type: 'PPO', state: 'CA', premium: 820, deductible: 1750 },
  ],
  Member: [
    { member_id: 'MBR-001', age: 34, gender: 'F', enrollment_date: '2023-01-15', plan_id: 'PLN-001' },
    { member_id: 'MBR-002', age: 45, gender: 'M', enrollment_date: '2022-06-01', plan_id: 'PLN-001' },
    { member_id: 'MBR-003', age: 28, gender: 'F', enrollment_date: '2024-01-01', plan_id: 'PLN-002' },
    { member_id: 'MBR-004', age: 52, gender: 'M', enrollment_date: '2021-03-15', plan_id: 'PLN-003' },
    { member_id: 'MBR-005', age: 39, gender: 'F', enrollment_date: '2023-09-01', plan_id: 'PLN-004' },
  ],
  Claim: [
    { claim_id: 'CLM-001', member_id: 'MBR-001', provider_id: 'PRV-001', claim_amount: 1250, service_date: '2024-02-15', diagnosis_code: 'J06.9' },
    { claim_id: 'CLM-002', member_id: 'MBR-002', provider_id: 'PRV-002', claim_amount: 3500, service_date: '2024-03-01', diagnosis_code: 'I10' },
    { claim_id: 'CLM-003', member_id: 'MBR-003', provider_id: 'PRV-001', claim_amount: 2100, service_date: '2024-03-10', diagnosis_code: 'M54.5' },
    { claim_id: 'CLM-004', member_id: 'MBR-004', provider_id: 'PRV-003', claim_amount: 8750, service_date: '2024-02-28', diagnosis_code: 'K21.0' },
    { claim_id: 'CLM-005', member_id: 'MBR-005', provider_id: 'PRV-002', claim_amount: 1875, service_date: '2024-03-05', diagnosis_code: 'E11.9' },
  ],
  Provider: [
    { provider_id: 'PRV-001', provider_name: 'Dr. Sarah Chen', specialty: 'Primary Care', network_status: 'In-Network' },
    { provider_id: 'PRV-002', provider_name: 'Dr. Michael Rodriguez', specialty: 'Cardiology', network_status: 'In-Network' },
    { provider_id: 'PRV-003', provider_name: 'Dr. Emily Watson', specialty: 'Orthopedics', network_status: 'In-Network' },
    { provider_id: 'PRV-004', provider_name: 'Dr. James Park', specialty: 'Primary Care', network_status: 'Out-of-Network' },
    { provider_id: 'PRV-005', provider_name: 'Dr. Lisa Thompson', specialty: 'Cardiology', network_status: 'In-Network' },
  ],
  Drug: [
    { ndc: '00093-0311-01', drug_name: 'Metformin 500mg', therapeutic_class: 'Antidiabetic', generic_available: true },
    { ndc: '00069-0150-01', drug_name: 'Lipitor 20mg', therapeutic_class: 'Statin', generic_available: true },
    { ndc: '00074-3799-13', drug_name: 'Humira 40mg', therapeutic_class: 'Immunosuppressant', generic_available: false },
    { ndc: '00002-4112-01', drug_name: 'Trulicity 1.5mg', therapeutic_class: 'Antidiabetic', generic_available: false },
    { ndc: '00078-0357-15', drug_name: 'Entresto 97/103mg', therapeutic_class: 'Cardiovascular', generic_available: false },
  ],
}

// ============================================================================
// Mock Counts (actual vs estimated)
// ============================================================================

export const mockCounts: Record<string, number> = {
  Plan: 1182,
  Member: 118943,
  Claim: 2734561,
  Provider: 8456,
  Drug: 14892,
}

// ============================================================================
// Complete Mock ScopeState
// ============================================================================

export const mockScopeState: ScopeState = {
  primary_entity: 'Plan',
  entities: mockEntities,
  relationships: mockRelationships,
  counts: mockCounts,
  samples: mockSamples,
  full_data: null,
  natural_language_summary: 'Analyzing PPO plans in CA, TX, NY, and FL with active members aged 18-65, including their claims over $1,000 from 2024, serviced by Primary Care, Cardiology, and Orthopedics providers.',
  confidence: 'high',
  active_tab: 'build_query',
  preview_loading: false,
  selected_preview_entity: 'Plan',
}

// ============================================================================
// Mock ScopeState Variants
// ============================================================================

export const mockScopeStateLoading: ScopeState = {
  ...mockScopeState,
  preview_loading: true,
  confidence: 'medium',
}

export const mockScopeStateLowConfidence: ScopeState = {
  ...mockScopeState,
  confidence: 'low',
  natural_language_summary: 'Attempting to analyze healthcare data. Some entity relationships may be incomplete.',
}

export const mockScopeStateMinimal: ScopeState = {
  primary_entity: 'Plan',
  entities: [mockEntities[0]], // Just the primary entity
  relationships: [],
  counts: { Plan: 1182 },
  samples: { Plan: mockSamples.Plan },
  full_data: null,
  natural_language_summary: 'Simple analysis of PPO plans.',
  confidence: 'high',
  active_tab: 'build_query',
  preview_loading: false,
  selected_preview_entity: 'Plan',
}

// ============================================================================
// Mock Intent Package
// ============================================================================

export const mockIntentPackage: IntentPackage = {
  schema_version: 1,
  title: 'Healthcare Plan Cost Analysis',
  description: 'Comprehensive analysis of PPO plan costs across key states to identify optimization opportunities.',
  summary: 'This analysis examines PPO plan costs and utilization patterns across CA, TX, NY, and FL. The goal is to identify cost drivers, understand geographic variations, and provide actionable recommendations for plan pricing strategy.',
  mission: {
    objective: 'Analyze PPO plan costs and utilization patterns across key states',
    why: 'To identify cost drivers and optimization opportunities for plan pricing strategy',
    success_looks_like: 'Clear understanding of cost variations by plan type, geography, and member demographics with actionable recommendations',
  },
  team_guidance: {
    expertise_needed: ['cost drivers', 'geographic variations', 'provider network efficiency'],
    capabilities_needed: ['analyze data', 'generate insights', 'create visualizations'],
    complexity_level: 'Moderate',
    complexity_notes: 'Multi-entity with geographic and plan type dimensions',
    collaboration_pattern: 'Coordinated',
    human_ai_handshake_points: ['validate cost assumptions', 'review recommendations'],
    workflow_pattern: 'OneTime',
  },
  conversation_transcript: 'User: I want to analyze healthcare plan costs...\nTheo: Great, let me understand your goals better...',
  iteration_history: [
    { version: 1, timestamp: '2024-03-15T10:00:00Z', change_description: 'Initial intent captured', user_feedback: '' },
    { version: 2, timestamp: '2024-03-15T10:05:00Z', change_description: 'Refined success criteria based on user feedback', user_feedback: '' },
  ],
  current_version: 2,
  created_at: '2024-03-15T10:00:00Z',
  confirmed: true,
}

// ============================================================================
// Mock Field Metadata (for field selection dropdowns)
// ============================================================================

export interface MockFieldMetadata {
  name: string
  dataType: 'string' | 'number' | 'date' | 'boolean'
}

export const mockFieldMetadata: Record<string, MockFieldMetadata[]> = {
  Plan: [
    { name: 'plan_id', dataType: 'string' },
    { name: 'plan_name', dataType: 'string' },
    { name: 'plan_type', dataType: 'string' },
    { name: 'state', dataType: 'string' },
    { name: 'premium', dataType: 'number' },
    { name: 'deductible', dataType: 'number' },
    { name: 'effective_date', dataType: 'date' },
    { name: 'termination_date', dataType: 'date' },
    { name: 'is_active', dataType: 'boolean' },
    { name: 'network_tier', dataType: 'string' },
  ],
  Member: [
    { name: 'member_id', dataType: 'string' },
    { name: 'first_name', dataType: 'string' },
    { name: 'last_name', dataType: 'string' },
    { name: 'age', dataType: 'number' },
    { name: 'gender', dataType: 'string' },
    { name: 'date_of_birth', dataType: 'date' },
    { name: 'enrollment_date', dataType: 'date' },
    { name: 'enrollment_status', dataType: 'string' },
    { name: 'plan_id', dataType: 'string' },
    { name: 'is_primary', dataType: 'boolean' },
  ],
  Claim: [
    { name: 'claim_id', dataType: 'string' },
    { name: 'member_id', dataType: 'string' },
    { name: 'provider_id', dataType: 'string' },
    { name: 'claim_amount', dataType: 'number' },
    { name: 'paid_amount', dataType: 'number' },
    { name: 'service_date', dataType: 'date' },
    { name: 'claim_date', dataType: 'date' },
    { name: 'diagnosis_code', dataType: 'string' },
    { name: 'procedure_code', dataType: 'string' },
    { name: 'claim_status', dataType: 'string' },
    { name: 'is_emergency', dataType: 'boolean' },
  ],
  Provider: [
    { name: 'provider_id', dataType: 'string' },
    { name: 'provider_name', dataType: 'string' },
    { name: 'specialty', dataType: 'string' },
    { name: 'npi', dataType: 'string' },
    { name: 'network_status', dataType: 'string' },
    { name: 'contract_date', dataType: 'date' },
    { name: 'is_accepting_patients', dataType: 'boolean' },
  ],
  Drug: [
    { name: 'ndc', dataType: 'string' },
    { name: 'drug_name', dataType: 'string' },
    { name: 'generic_name', dataType: 'string' },
    { name: 'therapeutic_class', dataType: 'string' },
    { name: 'unit_price', dataType: 'number' },
    { name: 'generic_available', dataType: 'boolean' },
    { name: 'requires_prior_auth', dataType: 'boolean' },
  ],
  Diagnosis: [
    { name: 'diagnosis_code', dataType: 'string' },
    { name: 'diagnosis_name', dataType: 'string' },
    { name: 'icd_version', dataType: 'string' },
    { name: 'category', dataType: 'string' },
    { name: 'is_chronic', dataType: 'boolean' },
  ],
  Procedure: [
    { name: 'procedure_code', dataType: 'string' },
    { name: 'procedure_name', dataType: 'string' },
    { name: 'cpt_code', dataType: 'string' },
    { name: 'category', dataType: 'string' },
    { name: 'average_cost', dataType: 'number' },
  ],
  Facility: [
    { name: 'facility_id', dataType: 'string' },
    { name: 'facility_name', dataType: 'string' },
    { name: 'facility_type', dataType: 'string' },
    { name: 'address', dataType: 'string' },
    { name: 'bed_count', dataType: 'number' },
    { name: 'is_in_network', dataType: 'boolean' },
  ],
  Network: [
    { name: 'network_id', dataType: 'string' },
    { name: 'network_name', dataType: 'string' },
    { name: 'network_type', dataType: 'string' },
    { name: 'effective_date', dataType: 'date' },
    { name: 'is_active', dataType: 'boolean' },
  ],
  Benefit: [
    { name: 'benefit_id', dataType: 'string' },
    { name: 'benefit_name', dataType: 'string' },
    { name: 'coverage_type', dataType: 'string' },
    { name: 'copay_amount', dataType: 'number' },
    { name: 'coinsurance_rate', dataType: 'number' },
    { name: 'requires_referral', dataType: 'boolean' },
  ],
}

// ============================================================================
// Available Entities (for Add Entity modal)
// ============================================================================

export const mockAvailableEntities: string[] = [
  'Plan',
  'Member',
  'Claim',
  'Provider',
  'Drug',
  'Diagnosis',
  'Procedure',
  'Facility',
  'Network',
  'Benefit',
]

// ============================================================================
// Helper function to create customized mock state
// ============================================================================

export function createMockScopeState(overrides: Partial<ScopeState> = {}): ScopeState {
  return {
    ...mockScopeState,
    ...overrides,
  }
}

export function createMockEntity(overrides: Partial<ScopeEntity> = {}): ScopeEntity {
  const entityType = overrides.entity_type || 'CustomEntity'
  return {
    entity_type: entityType,
    relevance_level: 'related',
    reasoning: 'Custom entity for testing',
    enabled: true,
    filters: [],
    fields_of_interest: [],
    estimated_count: 1000,
    query: `MATCH (n:${entityType}) RETURN DISTINCT n`,
    ...overrides,
  }
}

// ============================================================================
// Mock Entity Without Query (for testing "no query" state)
// ============================================================================

export const mockEntityWithoutQuery: ScopeEntity = {
  entity_type: 'Legacy',
  relevance_level: 'contextual',
  reasoning: 'Legacy entity without query support.',
  enabled: true,
  filters: [],
  fields_of_interest: [
    { field: 'legacy_id', justification: 'Primary identifier' },
    { field: 'legacy_name', justification: 'Display name' },
  ],
  estimated_count: 500,
  // No query field - tests the "no query available" state
}
