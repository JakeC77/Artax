"""
Live workflow test for Data Scope Recommendation.

This script demonstrates the complete end-to-end workflow:
1. Create a realistic intent (one-pager)
2. Fetch workspace schema from GraphQL API
3. Generate scope recommendation using AI agent
4. Execute recommendation and fetch matching nodes
5. Display results

Usage:
    python test_live_workflow.py                    # Quick build mode (no conversation)
    python test_live_workflow.py --interactive      # Interactive mode with streaming
    python test_live_workflow.py --events           # Event stream mode (shows frontend events)
    python test_live_workflow.py --debug            # Show all properties/fields and save outputs

Environment variables required:
    WORKSPACE_ID - Workspace UUID
    TENANT_ID - Tenant ID for authentication
    GRAPHQL_ENDPOINT (optional) - GraphQL endpoint URL
"""

import asyncio
import os
import sys
import argparse
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    # Try loading from multiple locations
    env_paths = [
        Path(__file__).parent / ".env",  # data_recommender/.env
        Path(__file__).parent.parent.parent / ".env",  # app/.env
        Path(__file__).parent.parent.parent.parent / ".env",  # project root/.env
    ]

    env_loaded = False
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ Loaded environment from: {env_path}")
            env_loaded = True
            break

    if not env_loaded:
        print("⚠️  No .env file found. Using environment variables only.")
        print(f"   Searched locations:")
        for env_path in env_paths:
            print(f"   - {env_path}")

except ImportError:
    print("⚠️  python-dotenv not installed. Using environment variables only.")
    print("   Install with: pip install python-dotenv")

from app.workflows.theo.models import IntentPackage, Mission, TeamBuildingGuidance
from app.workflows.data_recommender.agent import (
    recommend_scope,
    ScopeBuilder,
    GraphSchema,
    EntityType,
    PropertyInfo,
    RelationshipType
)
from app.workflows.data_recommender.executor import ScopeExecutor
from app.workflows.data_recommender.graphql_client import create_client
from app.workflows.data_recommender.schema_discovery import (
    fetch_workspace_schema as _fetch_workspace_schema,
    fetch_sample_data as _fetch_sample_data
)
from app.core.authenticated_graphql_client import run_graphql


# ========================================
# Mock Event Logger (for CLI debugging)
# ========================================

class MockEventLogger:
    """
    Mock log streamer that prints events as the frontend would receive them.

    This shows the EVENT STREAM order, which is what matters for frontend rendering.
    Use this to debug the workflow without connecting to a real GraphQL backend.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize mock event logger.

        Args:
            verbose: If True, show full metadata. If False, show summary only.
        """
        self.verbose = verbose
        self.events: List[Dict[str, Any]] = []

    async def log_event(
        self,
        event_type: str,
        message: str,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log an event (prints to console and stores for later review).

        Args:
            event_type: Type of event (agent_message, scope_update, clarification_needed, etc.)
            message: Event message
            agent_id: Agent that produced the event
            metadata: Additional event data
        """
        event = {
            "event_type": event_type,
            "message": message,
            "agent_id": agent_id,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        self.events.append(event)

        # Print event to console
        self._print_event(event)

    async def append_log(self, message: str):
        """Append to workflow log (for progress tracking)."""
        # Just print, don't store - these are internal logs
        print(f"\n📝 LOG: {message}")

    def _print_event(self, event: Dict[str, Any]):
        """Pretty-print an event to console."""
        event_type = event["event_type"]
        message = event["message"]
        metadata = event.get("metadata", {})

        # Color/style by event type
        print("\n" + "─" * 60)

        if event_type == "agent_message":
            print(f"💬 [AGENT_MESSAGE]")
            print(f"   {message}")

        elif event_type == "scope_update":
            print(f"📊 [SCOPE_UPDATE]")
            print(f"   Summary: {metadata.get('summary', message)}")
            print(f"   Confidence: {metadata.get('confidence', 'N/A')}")
            entities = metadata.get('entities', [])
            if entities:
                print(f"   Entities ({len(entities)}):")
                for e in entities:
                    entity_type = e.get('entity_type', 'Unknown')
                    filters = e.get('filters', [])
                    filter_summary = f" [{len(filters)} filters]" if filters else ""
                    print(f"      • {entity_type}{filter_summary}")
            relationships = metadata.get('relationships', [])
            if relationships:
                print(f"   Relationships ({len(relationships)}):")
                for r in relationships:
                    print(f"      • {r.get('from_entity')} → {r.get('to_entity')}")

        elif event_type == "clarification_needed":
            print(f"❓ [CLARIFICATION_NEEDED]")
            print(f"   Question: {metadata.get('question', message)}")
            if metadata.get('context'):
                print(f"   Context: {metadata.get('context')}")
            options = metadata.get('options', [])
            if options:
                print(f"   Options:")
                for i, opt in enumerate(options, 1):
                    rec = " ⭐" if opt.get('recommended') else ""
                    print(f"      {i}. {opt.get('label', 'N/A')}{rec}")
                    if self.verbose and opt.get('description'):
                        print(f"         {opt.get('description')}")

        elif event_type == "scope_finalized":
            print(f"✅ [SCOPE_FINALIZED]")
            print(f"   Summary: {metadata.get('summary', message)}")
            print(f"   Confidence: {metadata.get('confidence', 'N/A')}")
            entities = metadata.get('entities', [])
            print(f"   Entities: {len(entities)}")
            relationships = metadata.get('relationships', [])
            print(f"   Relationships: {len(relationships)}")

        elif event_type == "scope_awaiting_confirmation":
            print(f"⏸️  [SCOPE_AWAITING_CONFIRMATION]")
            print(f"   {message}")
            print(f"   Summary: {metadata.get('summary', 'N/A')}")
            print(f"   Entities: {metadata.get('entity_count', 0)}")
            print(f"   Relationships: {metadata.get('relationship_count', 0)}")
            print(f"\n   👉 Type 'confirm' to execute or 'reject' to cancel")

        elif event_type == "execution_started":
            print(f"  [EXECUTION_STARTED]")
            print(f"   {message}")
            entities = metadata.get('entities', [])
            if entities:
                print(f"   Entities to fetch: {', '.join(entities)}")

        elif event_type == "entity_filtering":
            print(f"🔍 [ENTITY_FILTERING]")
            print(f"   {message}")
            print(f"   API filters: {metadata.get('api_filter_count', 0)}")
            print(f"   Python filters: {metadata.get('python_filter_count', 0)}")

        elif event_type == "entity_execution_complete":
            print(f"✓ [ENTITY_COMPLETE]")
            print(f"   {metadata.get('entity_type', 'Unknown')}: {metadata.get('matches_after_filtering', 0)} matches")
            print(f"   Candidates fetched: {metadata.get('candidates_fetched', 0)}")

        elif event_type == "execution_complete":
            print(f"🎉 [EXECUTION_COMPLETE]")
            print(f"   {message}")
            print(f"   Total matches: {metadata.get('total_matches', 0)}")
            print(f"   Execution time: {metadata.get('execution_time_seconds', 0):.2f}s")
            matching = metadata.get('matching_node_ids', {})
            if matching:
                print(f"   Results by entity:")
                for entity, ids in matching.items():
                    print(f"      • {entity}: {len(ids)} nodes")

        elif event_type == "execution_error":
            print(f"❌ [EXECUTION_ERROR]")
            print(f"   {message}")

        elif event_type == "workflow_stage":
            print(f"⏳ [WORKFLOW_STAGE]")
            print(f"   {message}")

        elif event_type == "workflow_error":
            print(f"❌ [WORKFLOW_ERROR]")
            print(f"   {message}")

        elif event_type == "workflow_complete":
            print(f"🏁 [WORKFLOW_COMPLETE]")
            print(f"   {message}")

        else:
            print(f"📌 [{event_type.upper()}]")
            print(f"   {message}")

        # Show full metadata in verbose mode
        if self.verbose and metadata:
            print(f"\n   Raw metadata:")
            metadata_str = json.dumps(metadata, indent=6, default=str)
            # Truncate if too long
            if len(metadata_str) > 500:
                metadata_str = metadata_str[:500] + "..."
            print(f"   {metadata_str}")

        print("─" * 60)

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all logged events."""
        return self.events

    def print_summary(self):
        """Print summary of all events."""
        print("\n" + "=" * 60)
        print("EVENT STREAM SUMMARY")
        print("=" * 60)
        print(f"\nTotal events: {len(self.events)}")

        # Count by type
        type_counts: Dict[str, int] = {}
        for event in self.events:
            t = event["event_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        print("\nBy type:")
        for t, count in sorted(type_counts.items()):
            print(f"   {t}: {count}")

        print("\nEvent sequence:")
        for i, event in enumerate(self.events, 1):
            print(f"   {i}. {event['event_type']}")


# ========================================
# Schema Discovery Functions (CLI wrappers with console output)
# ========================================

async def fetch_workspace_schema(workspace_id: str, tenant_id: str, debug: bool = False) -> GraphSchema:
    """
    Fetch workspace schema from GraphQL API with CLI console output.

    Wraps the schema_discovery module function with pretty console output
    for the CLI test experience.

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        debug: If True, print detailed property and field information

    Returns:
        GraphSchema with entities and relationships
    """
    print("\n" + "="*70)
    print("FETCHING WORKSPACE SCHEMA")
    print("="*70)

    if debug:
        print("\n🔍 DEBUG MODE ENABLED - Showing all properties and fields")

    print(f"\n📊 Fetching schema from GraphQL API...")

    # Use the shared schema discovery function
    schema = await _fetch_workspace_schema(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        debug=debug
    )

    print(f"\n✓ Schema loaded:")
    print(f"   - {len(schema.entities)} node types")
    print(f"   - {sum(len(e.properties) for e in schema.entities)} total properties")
    print(f"   - {len(schema.relationships)} relationship types")

    if debug:
        print(f"\n📋 Entity Details:")
        for entity in schema.entities:
            print(f"\n   {entity.name}:")
            if entity.properties:
                for prop in entity.properties:
                    print(f"      • {prop.name} ({prop.type})")
            else:
                print(f"      (no properties)")

    return schema


async def fetch_sample_data(
    workspace_id: str,
    tenant_id: str,
    entity_types: List[str],
    samples_per_entity: int = 3,
    debug: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch sample data for specified entity types with CLI console output.

    Wraps the schema_discovery module function with pretty console output
    for the CLI test experience.

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        entity_types: List of entity types to sample
        samples_per_entity: Number of sample records per entity (default 3)
        debug: If True, print sample data

    Returns:
        Dict mapping entity_type -> list of property dicts
    """
    print("\n" + "="*70)
    print("FETCHING SAMPLE DATA")
    print("="*70)
    print(f"\n📊 Fetching {samples_per_entity} samples for {len(entity_types)} entity types...")

    # Use the shared schema discovery function
    sample_data = await _fetch_sample_data(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        entity_types=entity_types,
        samples_per_entity=samples_per_entity,
        debug=debug
    )

    # Print summary
    for entity_type, samples in sample_data.items():
        if samples:
            print(f"   ✓ {entity_type}: {len(samples)} samples")
            if debug:
                print(f"      Sample values:")
                for i, sample in enumerate(samples[:2], 1):
                    preview = {k: v for k, v in list(sample.items())[:5]}
                    print(f"         {i}. {preview}")
        else:
            print(f"   ⚠️  {entity_type}: No samples")

    total_samples = sum(len(s) for s in sample_data.values())
    print(f"\n✓ Sample data loaded: {total_samples} total samples")

    return sample_data


# ========================================
# Debug Output Functions
# ========================================

def get_debug_output_dir() -> Path:
    """Get or create the debug output directory."""
    debug_dir = Path(__file__).parent / "debug_output"
    debug_dir.mkdir(exist_ok=True)
    return debug_dir


def save_debug_output(data: Any, filename: str, debug: bool = False) -> Optional[Path]:
    """
    Save data to a JSON file in the debug output directory.

    Args:
        data: Data to save (must be JSON-serializable or have model_dump method)
        filename: Base filename (timestamp will be prepended)
        debug: Only save if debug mode is enabled

    Returns:
        Path to saved file, or None if not saved
    """
    if not debug:
        return None

    debug_dir = get_debug_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = debug_dir / f"{timestamp}_{filename}"

    # Handle Pydantic models
    if hasattr(data, 'model_dump'):
        json_data = data.model_dump(mode='json')
    else:
        json_data = data

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, default=str)

    print(f"\n💾 Debug output saved: {filepath}")
    return filepath


# ========================================
# Sample Intent (One-Pager)
# ========================================

def create_sample_intent() -> IntentPackage:
    """
    Create a realistic intent for testing.

    This represents a user's one-pager describing their objective.
    Relevant to PBM domain: Multi-entity analysis for cost and compliance.
    """
    return IntentPackage(
        title="Non-Compliant High-Cost Prescription Analysis",
        summary="Identify patients with prescriptions that have policy requirement violations and high costs in the last 90 days to reduce financial risk and improve compliance.",
        mission=Mission(
            objective="Find patients with non-compliant prescriptions and high medication costs",
            why="We need to proactively address policy violations before they result in claim denials or regulatory issues, especially for expensive medications.",
            success_looks_like="List of at-risk patients with their prescriptions, associated policy requirements, costs, and prescribers for intervention planning."
        ),
        team_guidance=TeamBuildingGuidance(
            expertise_needed=["pharmacy compliance", "cost management", "claims processing"],
            capabilities_needed=["data analysis", "pattern recognition", "risk assessment"],
            complexity_level="Moderate",
            collaboration_pattern="Coordinated"
        )
    )


def create_sample_intent_simple() -> IntentPackage:
    """
    Create a simple intent for testing with basic filtering.

    Relevant to PBM domain: Basic medication lookup.
    """
    return IntentPackage(
        title="High-Cost Medication Review",
        summary="Identify all medications in our formulary with average wholesale price above $500 to review pricing strategies",
        mission=Mission(
            objective="Get a list of high-cost medications currently in our formulary",
            why="Need to analyze our high-cost drug portfolio for potential cost-saving opportunities",
            success_looks_like="Clear list of expensive medications with pricing details for review"
        ),
        team_guidance=TeamBuildingGuidance(
            expertise_needed=["pharmaceutical pricing", "formulary management"],
            capabilities_needed=["data retrieval", "basic filtering"],
            complexity_level="Simple",
            collaboration_pattern="Solo"
        )
    )


def create_sample_intent_complex() -> IntentPackage:
    """
    Create a complex intent requiring multiple entities and relationships.

    Relevant to PBM domain: Advanced multi-entity analysis across plan, formulary, and utilization.
    """
    return IntentPackage(
        title="Formulary Optimization Across Plan Tiers",
        summary="Analyze medication utilization patterns across different plan types to identify opportunities for formulary optimization, focusing on therapeutic categories with high costs and multiple alternative treatments.",
        mission=Mission(
            objective="Identify medications and therapeutic categories where we can optimize formulary placement to reduce costs while maintaining quality of care",
            why="Rising medication costs are impacting plan sustainability. We need data-driven insights to negotiate better pricing, promote generics, and adjust tier placements without compromising patient outcomes.",
            success_looks_like="Comprehensive analysis showing: high-cost therapeutic categories, utilization by plan type, pricing variations across pharmacies, available alternatives in same drug class, and recommended formulary changes with projected savings."
        ),
        team_guidance=TeamBuildingGuidance(
            expertise_needed=["clinical pharmacy", "formulary management", "pricing analytics", "therapeutic equivalency"],
            capabilities_needed=["complex data analysis", "pattern recognition", "cost-benefit modeling", "relationship traversal"],
            complexity_level="Complex",
            collaboration_pattern="Orchestrated"
        )
    )


def create_sample_intent_mismatched() -> IntentPackage:
    """
    Create an intent that DOESN'T match the PBM schema.

    This tests the agent's clarification workflow when the intent doesn't align
    with available entities. The agent should ask for clarification.
    """
    return IntentPackage(
        title="Active Projects Review",
        summary="Show me all currently active projects in the system",
        mission=Mission(
            objective="Review all projects that are currently in active status",
            why="Need to understand current workload and resource allocation",
            success_looks_like="List of all active projects with basic details"
        ),
        team_guidance=TeamBuildingGuidance(
            expertise_needed=["project management"],
            capabilities_needed=["data retrieval"],
            complexity_level="Simple",
            collaboration_pattern="Solo"
        )
    )


# ========================================
# Main Workflow
# ========================================

async def run_workflow(
    workspace_id: str,
    tenant_id: str,
    intent: IntentPackage,
    debug: bool = False
):
    """
    Run the complete Data Scope Recommendation workflow.

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        intent: User intent (one-pager)
        debug: If True, show detailed property and field information
    """
    print("\n" + "="*70)
    print("DATA SCOPE RECOMMENDATION WORKFLOW - LIVE TEST")
    print("="*70)

    # Step 1: Fetch workspace schema
    schema = await fetch_workspace_schema(workspace_id, tenant_id, debug=debug)

    # Step 1.5: Fetch sample data for all entity types
    # This helps the agent understand actual value formats (e.g., "True" vs true)
    entity_types = [e.name for e in schema.entities]
    sample_data = await fetch_sample_data(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        entity_types=entity_types,
        samples_per_entity=3,
        debug=debug
    )

    # Step 2: Display intent
    print("\n" + "="*70)
    print("USER INTENT (ONE-PAGER)")
    print("="*70)
    print(f"\nTitle: {intent.title}")
    print(f"Summary: {intent.summary}")
    print(f"\nObjective: {intent.mission.objective}")
    print(f"Why: {intent.mission.why}")
    print(f"Success: {intent.mission.success_looks_like}")

    # Step 3: Generate scope recommendation
    print("\n" + "="*70)
    print("GENERATING SCOPE RECOMMENDATION")
    print("="*70)

    try:
        recommendation = await recommend_scope(
            intent_package=intent,
            graph_schema=schema,
            sample_data=sample_data,
        )

        print(f"\n✓ Recommendation generated")

        # Save recommendation in debug mode
        save_debug_output(recommendation, "scope_recommendation.json", debug=debug)

        # Display recommendation summary
        print("\n" + "-"*70)
        print("RECOMMENDATION SUMMARY")
        print("-"*70)

        print(f"\nSummary: {recommendation.summary}")
        print(f"Confidence: {recommendation.confidence_level}")
        print(f"Requires Clarification: {recommendation.requires_clarification}")

        if recommendation.requires_clarification:
            print("\n⚠️  Clarification Questions:")
            for i, question in enumerate(recommendation.clarification_questions, 1):
                print(f"   {i}. {question}")

        # Display full structured recommendation
        print("\n" + "-"*70)
        print("STRUCTURED RECOMMENDATION (Full Details)")
        print("-"*70)

        print(f"\n📋 Entities ({len(recommendation.entities)}):")
        for i, entity in enumerate(recommendation.entities, 1):
            print(f"\n  {i}. {entity.entity_type}")
            print(f"     Relevance Level: {entity.relevance_level}")
            print(f"     Reasoning: {entity.reasoning or 'N/A'}")

            if entity.filters:
                print(f"\n     Filters ({len(entity.filters)}):")
                for j, filter in enumerate(entity.filters, 1):
                    print(f"       {j}. Property: {filter.property}")
                    print(f"          Operator: {filter.operator.value}")
                    print(f"          Value: {filter.value}")
                    if filter.reasoning:
                        print(f"          Reasoning: {filter.reasoning}")
            else:
                print(f"\n     Filters: None")

            if entity.fields_of_interest:
                print(f"\n     Fields of Interest ({len(entity.fields_of_interest)}):")
                print(f"       {', '.join(entity.fields_of_interest)}")
            else:
                print(f"\n     Fields of Interest: All fields")

        if recommendation.relationships:
            print(f"\n\n🔗 Relationships ({len(recommendation.relationships)}):")
            for i, rel in enumerate(recommendation.relationships, 1):
                print(f"\n  {i}. {rel.from_entity} --[{rel.relationship_type}]--> {rel.to_entity}")
                if rel.reasoning:
                    print(f"     Reasoning: {rel.reasoning}")
        else:
            print(f"\n\n🔗 Relationships: None")

        # Display recommendation rationale if present
        if hasattr(recommendation, 'rationale') and recommendation.rationale:
            print(f"\n\n💭 Rationale:")
            print(f"   {recommendation.rationale}")

        # Step 4: Handle clarification loop if needed
        clarification_iteration = 0
        max_clarifications = 3  # Prevent infinite loops

        while recommendation.requires_clarification and clarification_iteration < max_clarifications:
            clarification_iteration += 1

            print("\n" + "="*70)
            print(f"CLARIFICATION NEEDED (Iteration {clarification_iteration})")
            print("="*70)

            # Prompt user for clarification responses
            print("\n💬 Please answer the following questions:")
            clarification_responses = []

            for i, question in enumerate(recommendation.clarification_questions, 1):
                print(f"\n{i}. {question}")
                response = input("   Your answer: ").strip()
                clarification_responses.append(response)

            # Create updated intent with clarification responses
            print("\n🔄 Re-running agent with your clarifications...")

            # Append clarification to intent summary
            clarification_text = "\n\nClarifications provided:\n" + "\n".join([
                f"Q: {q}\nA: {a}"
                for q, a in zip(recommendation.clarification_questions, clarification_responses)
            ])

            updated_intent = IntentPackage(
                title=intent.title,
                summary=intent.summary + clarification_text,
                mission=intent.mission,
                team_guidance=intent.team_guidance
            )

            # Re-run agent with clarified intent
            try:
                recommendation = await recommend_scope(
                    intent_package=updated_intent,
                    graph_schema=schema,
                    sample_data=sample_data,
                )

                # Update intent for next iteration (preserves all clarifications)
                intent = updated_intent

                print(f"\n✓ Updated recommendation generated")

                # Display updated recommendation summary
                print("\n" + "-"*70)
                print("UPDATED RECOMMENDATION SUMMARY")
                print("-"*70)

                print(f"\nSummary: {recommendation.summary}")
                print(f"Confidence: {recommendation.confidence_level}")
                print(f"Requires Clarification: {recommendation.requires_clarification}")

                if recommendation.requires_clarification:
                    print("\n⚠️  Still needs clarification:")
                    for i, question in enumerate(recommendation.clarification_questions, 1):
                        print(f"   {i}. {question}")
                else:
                    print("\n✅ Clarification resolved! Proceeding to execution...")

                # Display full structured recommendation
                print("\n" + "-"*70)
                print("UPDATED STRUCTURED RECOMMENDATION (Full Details)")
                print("-"*70)

                print(f"\n📋 Entities ({len(recommendation.entities)}):")
                for i, entity in enumerate(recommendation.entities, 1):
                    print(f"\n  {i}. {entity.entity_type}")
                    print(f"     Relevance Level: {entity.relevance_level}")
                    print(f"     Reasoning: {entity.reasoning or 'N/A'}")

                    if entity.filters:
                        print(f"\n     Filters ({len(entity.filters)}):")
                        for j, filter in enumerate(entity.filters, 1):
                            print(f"       {j}. Property: {filter.property}")
                            print(f"          Operator: {filter.operator.value}")
                            print(f"          Value: {filter.value}")
                            if filter.reasoning:
                                print(f"          Reasoning: {filter.reasoning}")
                    else:
                        print(f"\n     Filters: None")

                    if entity.fields_of_interest:
                        print(f"\n     Fields of Interest ({len(entity.fields_of_interest)}):")
                        print(f"       {', '.join(entity.fields_of_interest)}")
                    else:
                        print(f"\n     Fields of Interest: All fields")

                if recommendation.relationships:
                    print(f"\n\n🔗 Relationships ({len(recommendation.relationships)}):")
                    for i, rel in enumerate(recommendation.relationships, 1):
                        print(f"\n  {i}. {rel.from_entity} --[{rel.relationship_type}]--> {rel.to_entity}")
                        if rel.reasoning:
                            print(f"     Reasoning: {rel.reasoning}")
                else:
                    print(f"\n\n🔗 Relationships: None")

            except Exception as e:
                print(f"\n❌ Error during re-run: {type(e).__name__}: {str(e)}")
                break

        # Only stop if we hit max iterations AND still need clarification
        if clarification_iteration >= max_clarifications and recommendation.requires_clarification:
            print("\n⚠️  Maximum clarification iterations reached but still needs clarification. Stopping workflow.")
            return

        # Step 5: Execute recommendation (if clarification is resolved)
        if not recommendation.requires_clarification:
            print("\n" + "="*70)
            print("EXECUTING SCOPE RECOMMENDATION")
            print("="*70)

            # Create GraphQL client
            graphql_client = create_client(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )

            # Create executor
            executor = ScopeExecutor(
                tenant_id=tenant_id,
                graphql_client=graphql_client,
                debug=debug
            )

            print(f"\n⚙️  Executing scope against workspace...")

            result = await executor.execute(recommendation, schema)

            # Display results
            print("\n" + "-"*70)
            print("EXECUTION RESULTS")
            print("-"*70)

            print(f"\nSuccess: {result.success}")
            if result.error_message:
                print(f"Error: {result.error_message}")

            if result.warnings:
                print(f"\n⚠️  Warnings:")
                for warning in result.warnings:
                    print(f"   - {warning}")

            print(f"\n📊 Statistics:")
            print(f"   Total Candidates: {result.stats.total_candidates}")
            print(f"   Total Matches: {result.stats.total_matches}")
            print(f"   Execution Time: {result.stats.execution_time_seconds:.3f}s")

            print(f"\n📋 Matching Nodes by Entity:")
            for entity_type, node_ids in result.matching_node_ids.items():
                print(f"   {entity_type}: {len(node_ids)} nodes")

                # Show first few node IDs
                if node_ids:
                    sample = node_ids[:3]
                    print(f"      Sample IDs: {', '.join(sample)}")
                    if len(node_ids) > 3:
                        print(f"      ... and {len(node_ids) - 3} more")

            # Show detailed stats per entity
            if result.stats.entity_stats:
                print(f"\n📊 Per-Entity Statistics:")
                for entity_stat in result.stats.entity_stats:
                    print(f"\n   {entity_stat.entity_type}:")
                    print(f"      Candidates Fetched: {entity_stat.candidates_fetched}")
                    print(f"      Matches After Filtering: {entity_stat.matches_after_filtering}")
                    print(f"      API Filters Applied: {entity_stat.api_filters_applied}")
                    print(f"      Python Filters Applied: {entity_stat.python_filters_applied}")

                    if entity_stat.candidates_fetched > 0:
                        match_rate = (entity_stat.matches_after_filtering / entity_stat.candidates_fetched) * 100
                        print(f"      Match Rate: {match_rate:.1f}%")

            # Save execution result in debug mode
            save_debug_output(result, "execution_result.json", debug=debug)

        else:
            print("\n⏸️  Execution paused - clarification required")
            print("   Answer clarification questions and re-run workflow")

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)


# ========================================
# Interactive Workflow (Streaming Mode)
# ========================================

async def run_interactive_workflow(
    workspace_id: str,
    tenant_id: str,
    intent: IntentPackage,
    debug: bool = False
):
    """
    Run the interactive Data Scope Recommendation workflow.

    This uses the new ScopeBuilder class with streaming and tool-based
    conversation. The agent will:
    1. Stream text responses word-by-word
    2. Use update_scope() to show progress
    3. Use ask_clarification() for structured questions
    4. Use finalize_scope() when complete

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        intent: User intent (one-pager)
        debug: If True, show detailed property and field information
    """
    print("\n" + "="*70)
    print("DATA SCOPE RECOMMENDATION - INTERACTIVE MODE")
    print("="*70)

    # Step 1: Fetch workspace schema
    schema = await fetch_workspace_schema(workspace_id, tenant_id, debug=debug)

    # Step 2: Fetch sample data
    entity_types = [e.name for e in schema.entities]
    sample_data = await fetch_sample_data(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        entity_types=entity_types,
        samples_per_entity=3,
        debug=debug
    )

    # Step 3: Display intent
    print("\n" + "="*70)
    print("USER INTENT (ONE-PAGER)")
    print("="*70)
    print(f"\nTitle: {intent.title}")
    print(f"Summary: {intent.summary}")
    print(f"\nObjective: {intent.mission.objective}")
    print(f"Why: {intent.mission.why}")
    print(f"Success: {intent.mission.success_looks_like}")

    # Step 4: Start interactive conversation
    print("\n" + "="*70)
    print("STARTING SCOPE INTERVIEW")
    print("="*70)

    builder = ScopeBuilder()

    try:
        recommendation = await builder.start_conversation(
            intent_package=intent,
            graph_schema=schema,
            sample_data=sample_data,
            message_source=None,  # Use stdin for CLI
            log_streamer=None     # No remote logging in CLI mode
        )

        if recommendation is None:
            print("\n❌ Scope interview cancelled.")
            return

        print("\n✓ Scope recommendation finalized!")

        # Save recommendation in debug mode
        save_debug_output(recommendation, "scope_recommendation.json", debug=debug)

        # Display final recommendation
        print("\n" + "-"*70)
        print("FINAL RECOMMENDATION")
        print("-"*70)

        print(f"\nSummary: {recommendation.summary}")
        print(f"Confidence: {recommendation.confidence_level}")

        print(f"\n📋 Entities ({len(recommendation.entities)}):")
        for i, entity in enumerate(recommendation.entities, 1):
            print(f"\n  {i}. {entity.entity_type}")
            print(f"     Relevance Level: {entity.relevance_level}")
            if entity.reasoning:
                print(f"     Reasoning: {entity.reasoning}")

            if entity.filters:
                print(f"\n     Filters ({len(entity.filters)}):")
                for j, filter in enumerate(entity.filters, 1):
                    print(f"       {j}. {filter.property} {filter.operator.value} {filter.value}")
                    if filter.reasoning:
                        print(f"          Reasoning: {filter.reasoning}")

        if recommendation.relationships:
            print(f"\n🔗 Relationships ({len(recommendation.relationships)}):")
            for i, rel in enumerate(recommendation.relationships, 1):
                print(f"  {i}. {rel.from_entity} --[{rel.relationship_type}]--> {rel.to_entity}")

        # Step 5: Ask if user wants to execute
        print("\n" + "-"*70)
        execute = input("\nExecute this scope? (y/n) [default: y]: ").strip().lower() or "y"

        if execute == "y":
            print("\n" + "="*70)
            print("EXECUTING SCOPE RECOMMENDATION")
            print("="*70)

            graphql_client = create_client(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )

            executor = ScopeExecutor(
                tenant_id=tenant_id,
                graphql_client=graphql_client,
                debug=debug
            )

            print(f"\n⚙️  Executing scope against workspace...")

            result = await executor.execute(recommendation, schema)

            print("\n" + "-"*70)
            print("EXECUTION RESULTS")
            print("-"*70)

            print(f"\nSuccess: {result.success}")
            if result.error_message:
                print(f"Error: {result.error_message}")

            print(f"\n📊 Statistics:")
            print(f"   Total Candidates: {result.stats.total_candidates}")
            print(f"   Total Matches: {result.stats.total_matches}")
            print(f"   Execution Time: {result.stats.execution_time_seconds:.3f}s")

            print(f"\n📋 Matching Nodes by Entity:")
            for entity_type, node_ids in result.matching_node_ids.items():
                print(f"   {entity_type}: {len(node_ids)} nodes")
                if node_ids:
                    sample = node_ids[:3]
                    print(f"      Sample IDs: {', '.join(sample)}")
                    if len(node_ids) > 3:
                        print(f"      ... and {len(node_ids) - 3} more")

            save_debug_output(result, "execution_result.json", debug=debug)

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)


# ========================================
# Event Stream Workflow (shows frontend events)
# ========================================

async def run_event_stream_workflow(
    workspace_id: str,
    tenant_id: str,
    intent: IntentPackage,
    debug: bool = False,
    verbose: bool = False
):
    """
    Run the workflow with MockEventLogger to show events as frontend receives them.

    This mode shows the EVENT STREAM that the frontend would receive, which is
    the correct order for rendering (unlike CLI streaming which has ordering issues).

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        intent: User intent (one-pager)
        debug: If True, show detailed property and field information
        verbose: If True, show full event metadata
    """
    print("\n" + "="*70)
    print("DATA SCOPE RECOMMENDATION - EVENT STREAM MODE")
    print("="*70)
    print("\nThis shows events as the frontend would receive them.")
    print("Watch the [EVENT_TYPE] tags to see what the frontend renders.\n")

    # Step 1: Fetch workspace schema (with minimal output)
    print("📊 Fetching workspace schema...")
    schema = await _fetch_workspace_schema(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        debug=False  # Quiet mode for event stream testing
    )
    print(f"   ✓ {len(schema.entities)} entities, {len(schema.relationships)} relationships")

    # Step 2: Fetch sample data
    print("📊 Fetching sample data...")
    entity_types = [e.name for e in schema.entities]
    sample_data = await _fetch_sample_data(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        entity_types=entity_types,
        samples_per_entity=3,
        debug=False
    )
    print(f"   ✓ {sum(len(s) for s in sample_data.values())} samples")

    # Step 3: Display intent briefly
    print(f"\n📋 Intent: {intent.title}")
    print(f"   {intent.mission.objective}")

    # Step 4: Create mock event logger
    event_logger = MockEventLogger(verbose=verbose)

    # Log workflow start
    await event_logger.log_event(
        event_type="workflow_stage",
        message="Starting scope interview...",
        agent_id="theo"
    )

    # Step 5: Run scope builder with event logger
    print("\n" + "="*70)
    print("STARTING SCOPE INTERVIEW (Event Stream)")
    print("="*70)

    builder = ScopeBuilder()

    try:
        recommendation = await builder.start_conversation(
            intent_package=intent,
            graph_schema=schema,
            sample_data=sample_data,
            message_source=None,  # Use stdin for CLI
            log_streamer=event_logger  # Use mock event logger!
        )

        if recommendation is None:
            await event_logger.log_event(
                event_type="workflow_error",
                message="Scope interview cancelled",
                agent_id="theo"
            )
            event_logger.print_summary()
            return

        # Log finalization (scope ready for confirmation)
        await event_logger.log_event(
            event_type="scope_finalized",
            message=recommendation.summary,
            agent_id="theo",
            metadata={
                "summary": recommendation.summary,
                "confidence": recommendation.confidence_level,
                "entities": [e.model_dump() for e in recommendation.entities],
                "relationships": [r.model_dump() for r in recommendation.relationships]
            }
        )

        # Emit awaiting confirmation event
        await event_logger.log_event(
            event_type="scope_awaiting_confirmation",
            message="Scope ready for confirmation. Send 'scope_confirmed' to execute.",
            agent_id="theo",
            metadata={
                "summary": recommendation.summary,
                "confidence": recommendation.confidence_level,
                "entity_count": len(recommendation.entities),
                "relationship_count": len(recommendation.relationships),
            }
        )

        # Wait for user confirmation (CLI simulation)
        print("\n" + "=" * 60)
        confirm_input = input("Type 'confirm' to execute scope, 'reject' to cancel: ").strip().lower()

        if confirm_input == "confirm":
            # Emit confirmation received
            await event_logger.log_event(
                event_type="scope_confirmed",
                message="Scope confirmed by user, starting execution",
                agent_id="user"
            )

            # Execute scope
            await event_logger.log_event(
                event_type="execution_started",
                message=f"Starting scope execution for {len(recommendation.entities)} entities...",
                agent_id="theo",
                metadata={
                    "entity_count": len(recommendation.entities),
                    "entities": [e.entity_type for e in recommendation.entities],
                }
            )

            # Create GraphQL client and executor
            graphql_client = create_client(
                workspace_id=workspace_id,
                tenant_id=tenant_id
            )

            executor = ScopeExecutor(
                tenant_id=tenant_id,
                log_streamer=event_logger,  # Pass event logger for streaming
                graphql_client=graphql_client,
                debug=debug
            )

            # Execute
            result = await executor.execute(recommendation, schema)

            # Emit per-entity results
            if result and result.stats.entity_stats:
                for entity_stat in result.stats.entity_stats:
                    await event_logger.log_event(
                        event_type="entity_execution_complete",
                        message=f"{entity_stat.entity_type}: {entity_stat.matches_after_filtering} matches",
                        agent_id="theo",
                        metadata={
                            "entity_type": entity_stat.entity_type,
                            "candidates_fetched": entity_stat.candidates_fetched,
                            "matches_after_filtering": entity_stat.matches_after_filtering,
                            "api_filters_applied": entity_stat.api_filters_applied,
                            "python_filters_applied": entity_stat.python_filters_applied,
                        }
                    )

            # Emit completion
            total_matches = result.stats.total_matches if result else 0
            await event_logger.log_event(
                event_type="execution_complete",
                message=f"Scope execution complete: {total_matches} total matches",
                agent_id="theo",
                metadata={
                    "total_matches": total_matches,
                    "matching_node_ids": result.matching_node_ids if result else {},
                    "execution_time_seconds": result.stats.execution_time_seconds if result else 0,
                }
            )

            await event_logger.log_event(
                event_type="workflow_complete",
                message=f"Data scope workflow complete: {total_matches} total matches",
                agent_id="theo",
            )

        else:
            # Scope rejected
            await event_logger.log_event(
                event_type="scope_rejected",
                message="Scope rejected by user",
                agent_id="user"
            )

        # Print event summary
        event_logger.print_summary()

        # Save events in debug mode
        if debug:
            save_debug_output(event_logger.get_events(), "event_stream.json", debug=True)

    except Exception as e:
        await event_logger.log_event(
            event_type="workflow_error",
            message=f"Error: {type(e).__name__}: {str(e)}",
            agent_id="theo"
        )
        event_logger.print_summary()
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)


# ========================================
# Entry Point
# ========================================

async def main():
    """Main entry point for live workflow test."""

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Data Scope Recommendation Workflow - Live Test",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode: show all properties/fields and save outputs to debug_output/"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Enable interactive mode: use streaming conversation with ScopeBuilder"
    )
    parser.add_argument(
        "--events", "-e",
        action="store_true",
        help="Enable event stream mode: show events as frontend would receive them"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full event metadata (use with --events)"
    )
    args = parser.parse_args()

    # Get environment variables
    workspace_id = os.getenv("WORKSPACE_ID")
    tenant_id = os.getenv("TENANT_ID")

    if not workspace_id or not tenant_id:
        print("❌ Error: Missing required environment variables")
        print("\nRequired:")
        print("  WORKSPACE_ID - Workspace UUID")
        print("  TENANT_ID - Tenant ID for authentication")
        print("\nOptional:")
        print("  GRAPHQL_ENDPOINT - GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)")
        print("\nExample:")
        print('  export WORKSPACE_ID="123e4567-e89b-12d3-a456-426614174000"')
        print('  export TENANT_ID="tenant_123"')
        print('  python test_live_workflow.py')
        return

    # Choose intent variant
    print("\nSelect intent variant:")
    print("  1. Simple (High-Cost Medication Review)")
    print("  2. Complex (Non-Compliant High-Cost Prescriptions)")
    print("  3. Very Complex (Formulary Optimization)")
    print("  4. Mismatched (Active Projects - tests clarification)")

    choice = input("\nEnter choice (1-4) [default: 2]: ").strip() or "2"

    if choice == "1":
        intent = create_sample_intent_simple()
    elif choice == "3":
        intent = create_sample_intent_complex()
    elif choice == "4":
        intent = create_sample_intent_mismatched()
    else:
        intent = create_sample_intent()

    # Run workflow based on mode
    if args.events:
        await run_event_stream_workflow(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            intent=intent,
            debug=args.debug,
            verbose=args.verbose
        )
    elif args.interactive:
        await run_interactive_workflow(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            intent=intent,
            debug=args.debug
        )
    else:
        await run_workflow(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            intent=intent,
            debug=args.debug
        )


if __name__ == "__main__":
    asyncio.run(main())
