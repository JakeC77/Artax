"""
Test script for V2 Analysis Workflow (Schema + Tools Architecture).

This is a clean, minimal test that runs:
- 1 analysis using cypher_query tool
- 1 scenario using cypher_query tool

Usage:
    python -m app.workflows.analysis.test_v2_workflow

Prerequisites:
    - GraphQL server running (or use --mock flag)
    - Valid workspace with data
    - API key for configured model provider (GOOGLE_API_KEY, OPENAI_API_KEY, etc.)
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Setup logging EARLY
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Silence noisy loggers
logging.getLogger("azure.identity").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load .env file via Config import (must happen before logfire setup)
from app.config import Config

# ============================================================================
# Logfire Instrumentation for pydantic-ai observability
# ============================================================================
def setup_logfire():
    """Configure Logfire observability."""
    if not Config.LOGFIRE_ENABLED:
        logger.info("Logfire disabled (LOGFIRE_ENABLED=false)")
        return False

    try:
        import logfire

        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        logfire_dir = repo_root / ".logfire"

        logfire.configure(
            token=Config.LOGFIRE_TOKEN,
            service_name="analysis-workflow-v2-test",
            send_to_logfire='if-token-present',
            config_dir=logfire_dir if logfire_dir.exists() else None,
        )
        logfire.instrument_pydantic_ai()
        logger.info("Logfire enabled - view traces at https://logfire.pydantic.dev")
        return True
    except ImportError:
        logger.info("Logfire not installed - run 'pip install logfire' for model call observability")
        return False
    except Exception as e:
        logger.warning(f"Logfire setup failed: {e}")
        return False

setup_logfire()

# Check for mock mode BEFORE imports that use graphql
MOCK_MODE = "--mock" in sys.argv

# ============================================================================
# Configuration
# ============================================================================

# Test workspace (update these for your environment)
TEST_WORKSPACE_ID = "ffaaa54d-bdd7-4ca1-901f-1ebdb2529ada"
TEST_TENANT_ID = "00000000-0000-0000-0000-000000000000"
TEST_RUN_ID = "00000000-0000-0000-0000-000000000001"

MOCK_INTENT_PACKAGE = {
    "title": "Specialty Drug Cost Optimization Analysis",
    "mission": {
        "why": "Specialty drugs represent a disproportionate share of pharmacy spend, often 1-2% of claims but 50%+ of costs. Understanding our specialty drug utilization patterns and comparing them to industry benchmarks is critical for cost containment strategy.",
        "objective": "Analyze specialty drug claims in the workspace to identify high-cost outliers, utilization patterns by member demographics, and opportunities for cost optimization. Compare findings against current industry benchmarks for specialty drug management.",
        "success_looks_like": "A data-driven analysis that (1) quantifies specialty vs non-specialty spend distribution, (2) identifies the top cost drivers, (3) correlates high utilization with member characteristics, and (4) provides actionable recommendations backed by external benchmark data."
    },
    "summary": "Comprehensive specialty drug cost analysis with industry benchmarking",
    "description": """Perform a multi-phase analysis:

PHASE 1 - Data Discovery:
- Query the graph to understand what claim and member data is available
- Identify the specialty drug claims (drug_class = 'Specialty')
- Calculate total spend by drug class

PHASE 2 - Deep Dive Analysis:
- Find the highest-cost specialty claims and identify patterns
- Analyze member demographics (age distribution) for specialty drug users vs general population
- Look for members with multiple high-cost claims

PHASE 3 - External Benchmarking:
- Search for current specialty drug cost trends and benchmarks (2024-2025 data)
- Research best practices for specialty drug cost management
- Find industry statistics on specialty-to-total-spend ratios

PHASE 4 - Synthesis:
- Compare our data against industry benchmarks
- Identify gaps or opportunities
- Provide specific, actionable recommendations

This analysis requires both internal data exploration via cypher queries AND external research via web search to provide context and benchmarking.""",
    "team_guidance": {
        "complexity_level": "Complex",
        "workflow_pattern": "MultiPhase"
    }
}


# ============================================================================
# Mock GraphQL for offline testing
# ============================================================================

MOCK_WORKSPACE_ITEMS = [
    {"workspaceItemId": "wi1", "graphNodeId": "claim-001", "labels": ["Claim"]},
    {"workspaceItemId": "wi2", "graphNodeId": "claim-002", "labels": ["Claim"]},
    {"workspaceItemId": "wi3", "graphNodeId": "claim-003", "labels": ["Claim"]},
    {"workspaceItemId": "wi4", "graphNodeId": "member-001", "labels": ["Member"]},
    {"workspaceItemId": "wi5", "graphNodeId": "member-002", "labels": ["Member"]},
]

MOCK_CYPHER_RESULTS = {
    # Mock results for common Cypher queries
    "MATCH (c:Claim)": [
        {"id": "claim-001", "labels": ["Claim"], "properties": [
            {"key": "claim_id", "value": "CLM001"},
            {"key": "paid_amount", "value": 1500.00},
            {"key": "drug_class", "value": "Specialty"}
        ]},
        {"id": "claim-002", "labels": ["Claim"], "properties": [
            {"key": "claim_id", "value": "CLM002"},
            {"key": "paid_amount", "value": 250.00},
            {"key": "drug_class", "value": "Generic"}
        ]},
        {"id": "claim-003", "labels": ["Claim"], "properties": [
            {"key": "claim_id", "value": "CLM003"},
            {"key": "paid_amount", "value": 3200.00},
            {"key": "drug_class", "value": "Specialty"}
        ]},
    ],
    "MATCH (m:Member)": [
        {"id": "member-001", "labels": ["Member"], "properties": [
            {"key": "member_id", "value": "MEM001"},
            {"key": "name", "value": "John Doe"},
            {"key": "age", "value": 45}
        ]},
        {"id": "member-002", "labels": ["Member"], "properties": [
            {"key": "member_id", "value": "MEM002"},
            {"key": "name", "value": "Jane Smith"},
            {"key": "age", "value": 52}
        ]},
    ],
}

MOCK_SCHEMA = {
    "graphNodeTypes": ["Claim", "Member"],
    "Claim": {
        "properties": [
            {"name": "claim_id", "dataType": "string"},
            {"name": "paid_amount", "dataType": "numeric"},
            {"name": "drug_class", "dataType": "string"},
        ],
        "relationships": ["FILED_BY"]
    },
    "Member": {
        "properties": [
            {"name": "member_id", "dataType": "string"},
            {"name": "name", "dataType": "string"},
            {"name": "age", "dataType": "integer"},
        ],
        "relationships": ["FILED_CLAIM"]
    }
}


async def mock_graphql_fetch(query: str, variables: dict, tenant_id: str, timeout: float = 30):
    """Mock GraphQL fetch for offline testing."""
    logger.info(f"[MOCK] GraphQL query: {query[:80]}...")

    # Handle workspace items query
    if "workspaceItems" in query:
        return {"workspaceItems": MOCK_WORKSPACE_ITEMS}

    # Handle node types query
    if "graphNodeTypes" in query:
        return {"graphNodeTypes": MOCK_SCHEMA["graphNodeTypes"]}

    # Handle property metadata query
    if "graphNodePropertyMetadata" in query:
        node_type = variables.get("type", "")
        if node_type in MOCK_SCHEMA:
            return {"graphNodePropertyMetadata": MOCK_SCHEMA[node_type]["properties"]}
        return {"graphNodePropertyMetadata": []}

    # Handle relationship types query
    if "graphNodeRelationshipTypes" in query:
        node_type = variables.get("type", "")
        if node_type in MOCK_SCHEMA:
            return {"graphNodeRelationshipTypes": MOCK_SCHEMA[node_type]["relationships"]}
        return {"graphNodeRelationshipTypes": []}

    # Handle semantic entities query
    if "semanticEntities" in query:
        return {"semanticEntities": [
            {"semanticEntityId": "1", "name": "Claim", "description": "Insurance claim"},
            {"semanticEntityId": "2", "name": "Member", "description": "Plan member"},
        ]}

    # Handle semantic fields query
    if "semanticFields" in query:
        return {"semanticFields": [
            {"semanticFieldId": "1", "semanticEntityId": "1", "name": "paid_amount", "dataType": "numeric", "rangeInfo": '{"min": 0, "max": 10000}'},
            {"semanticFieldId": "2", "semanticEntityId": "2", "name": "age", "dataType": "integer", "rangeInfo": '{"min": 18, "max": 100}'},
        ]}

    # Handle Cypher queries
    if "graphNodesByCypher" in query:
        cypher = variables.get("cypherQuery", "")
        # Find matching mock results
        for pattern, results in MOCK_CYPHER_RESULTS.items():
            if pattern in cypher:
                return {"graphNodesByCypher": results}
        # Default: return all claims
        return {"graphNodesByCypher": MOCK_CYPHER_RESULTS["MATCH (c:Claim)"]}

    # Handle mutations (no-op for testing)
    if "mutation" in query.lower():
        return {"success": True}

    return {}


# ============================================================================
# Mock SSE Logger
# ============================================================================

class MockSSELogger:
    """Mock SSE logger that prints events to console."""

    def __init__(self, run_id: str, tenant_id: str):
        self.run_id = run_id
        self.tenant_id = tenant_id

    async def log_event(self, event_type: str, message: str, agent_id: str = None, metadata: dict = None):
        icon = {
            "status": "📋",
            "message": "💬",
            "warning": "⚠️",
            "error": "❌",
            "complete": "✅",
        }.get(event_type, "•")
        logger.info(f"{icon} [{event_type}] {message}")
        if metadata and event_type in ("error", "warning"):
            logger.info(f"   metadata: {json.dumps(metadata, indent=2)}")


async def mock_sse_logger_factory(run_id: str, tenant_id: str):
    """Factory function for mock SSE logger."""
    return MockSSELogger(run_id, tenant_id)


# ============================================================================
# Mock Setup Helper
# ============================================================================

def setup_mocks():
    """Setup mock GraphQL before any imports."""
    import app.core.authenticated_graphql_client as graphql_client
    graphql_client.run_graphql = mock_graphql_fetch
    logger.info("Mock GraphQL installed")


# Apply mock EARLY if needed (before workflow imports)
if MOCK_MODE:
    setup_mocks()


# ============================================================================
# Test Functions
# ============================================================================

async def test_v2_workflow(use_mock: bool = False):
    """Test the V2 analysis workflow (schema + tools)."""
    from app.workflows.analysis_workflow import AnalysisWorkflow
    from app.workflows.analysis.config import load_config

    logger.info("=" * 60)
    logger.info("V2 Analysis Workflow Test (Schema + Tools)")
    logger.info("=" * 60)

    # Setup mocks if requested (redundant if already done, but safe)
    if use_mock:
        logger.info("Using mock GraphQL (offline mode)")
        setup_mocks()

        import app.core.graphql_logger as graphql_logger
        graphql_logger.ScenarioRunLogger = MockSSELogger

    # Load config from config.yaml (includes model settings for Gemini)
    config = load_config()
    # Override for minimal testing
    config.max_analyses = 1
    config.max_scenarios_per_analysis = 1
    config.max_scenarios_total = 1

    logger.info(f"Config: max_analyses={config.max_analyses}")
    logger.info(f"Config: max_scenarios_per_analysis={config.max_scenarios_per_analysis}")
    logger.info(f"Config: planner_model={config.planner_model}")
    logger.info(f"Config: executor_model={config.executor_model}")

    # Create workflow
    workflow = AnalysisWorkflow(config=config)

    # Create test event
    event = {
        "RunId": TEST_RUN_ID,
        "WorkspaceId": TEST_WORKSPACE_ID,
        "TenantId": TEST_TENANT_ID,
        "ScenarioId": None,
        "Inputs": json.dumps({
            "intent_package": MOCK_INTENT_PACKAGE
        })
    }

    logger.info("")
    logger.info("Starting workflow execution...")
    logger.info("")

    # Execute workflow
    try:
        result = await workflow.execute(event)

        logger.info("")
        logger.info("=" * 60)
        logger.info("Workflow Complete")
        logger.info("=" * 60)
        logger.info(f"Success: {result.success}")
        logger.info(f"Duration: {result.duration_seconds:.2f}s")
        logger.info(f"Result: {result.result}")

        if not result.success:
            logger.error(f"Error: {result.error}")

        return result

    except Exception as e:
        logger.exception(f"Workflow failed with exception: {e}")
        raise


async def test_context_package_only(use_mock: bool = False):
    """Test just the context package building (no LLM calls)."""
    from app.workflows.analysis.context_package import build_context_package, build_cypher_guide

    logger.info("=" * 60)
    logger.info("Context Package Test")
    logger.info("=" * 60)

    # Setup mocks if requested (redundant if already done, but safe)
    if use_mock:
        logger.info("Using mock GraphQL (offline mode)")
        setup_mocks()

    # Build context package
    logger.info(f"Building context package for workspace {TEST_WORKSPACE_ID[:8]}...")

    context = await build_context_package(
        workspace_id=TEST_WORKSPACE_ID,
        tenant_id=TEST_TENANT_ID,
        timeout_seconds=60
    )

    # Print summary
    logger.info("")
    logger.info("Context Package Summary:")
    logger.info(f"  Total nodes: {context.total_nodes}")
    logger.info(f"  Entity types: {list(context.entity_counts.keys())}")
    logger.info(f"  Entity counts: {context.entity_counts}")
    logger.info(f"  Relationship types: {len(context.relationship_schemas)}")

    # Print prompt string
    prompt_str = context.to_prompt_string()
    logger.info("")
    logger.info("Prompt string preview (first 2000 chars):")
    logger.info("-" * 40)
    logger.info(prompt_str[:2000])
    if len(prompt_str) > 2000:
        logger.info(f"... ({len(prompt_str)} total chars)")

    # Print cypher guide
    cypher_guide = build_cypher_guide(context, labels_exist=context.labels_exist_in_graph)
    logger.info("")
    logger.info("Cypher guide preview (first 1500 chars):")
    logger.info("-" * 40)
    logger.info(cypher_guide[:1500])

    # Print workspace node IDs (for tool scoping)
    logger.info("")
    logger.info("Workspace node IDs (for cypher_query scoping):")
    for entity_type, node_ids in context.workspace_node_ids.items():
        logger.info(f"  {entity_type}: {len(node_ids)} nodes")
        if node_ids:
            logger.info(f"    Sample: {node_ids[:3]}")

    return context


async def test_cypher_tool_only(use_mock: bool = False):
    """Test the cypher_query tool in isolation."""
    from app.tools.cypher_query import cypher_query, _inject_workspace_scope

    logger.info("=" * 60)
    logger.info("Cypher Query Tool Test")
    logger.info("=" * 60)

    # Setup mocks if requested (redundant if already done, but safe)
    if use_mock:
        logger.info("Using mock GraphQL (offline mode)")
        setup_mocks()

    # Test scope injection
    logger.info("")
    logger.info("Testing scope injection:")

    test_queries = [
        "MATCH (c:Claim) WHERE c.paid_amount > 1000 RETURN c",
        "MATCH (m:Member)-[:FILED_CLAIM]->(c:Claim) RETURN m, c",
        "MATCH (c:Claim) RETURN c.drug_class, count(c) as count",
    ]

    workspace_node_ids = {
        "Claim": ["claim-001", "claim-002", "claim-003"],
        "Member": ["member-001", "member-002"],
    }

    for query in test_queries:
        scoped = _inject_workspace_scope(query, workspace_node_ids)
        logger.info(f"  Original: {query}")
        logger.info(f"  Scoped:   {scoped[:200]}...")
        logger.info("")

    # Test actual tool execution (requires mock or real GraphQL)
    logger.info("Testing tool execution:")

    # Create mock RunContext
    class MockRunContext:
        def __init__(self, deps):
            self.deps = deps

    ctx = MockRunContext({
        "workspace_id": TEST_WORKSPACE_ID,
        "tenant_id": TEST_TENANT_ID,
        "workspace_node_ids": workspace_node_ids,
    })

    # Execute test query
    result = await cypher_query(
        ctx,
        query="MATCH (c:Claim) RETURN c.claim_id, c.paid_amount ORDER BY c.paid_amount DESC",
        max_results=10
    )

    logger.info(f"  Query result:")
    logger.info(f"    Count: {result.get('count')}")
    logger.info(f"    Truncated: {result.get('truncated')}")
    logger.info(f"    Error: {result.get('error')}")
    if result.get('results'):
        logger.info(f"    Sample results: {result['results'][:2]}")

    return result


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Test V2 Analysis Workflow")
    parser.add_argument("--mock", action="store_true", help="Use mock GraphQL (offline mode)")
    parser.add_argument("--context-only", action="store_true", help="Test context package only (no LLM)")
    parser.add_argument("--cypher-only", action="store_true", help="Test cypher tool only (no LLM)")
    parser.add_argument("--workspace", type=str, help="Workspace ID to test with")
    parser.add_argument("--tenant", type=str, help="Tenant ID to test with")

    args = parser.parse_args()

    # Override test IDs if provided
    global TEST_WORKSPACE_ID, TEST_TENANT_ID
    if args.workspace:
        TEST_WORKSPACE_ID = args.workspace
    if args.tenant:
        TEST_TENANT_ID = args.tenant

    print("")
    print("=" * 60)
    print("V2 Analysis Workflow Test")
    print("=" * 60)
    print(f"Workspace: {TEST_WORKSPACE_ID}")
    print(f"Tenant: {TEST_TENANT_ID}")
    print(f"Mock mode: {args.mock}")
    print("")

    # Run appropriate test
    if args.context_only:
        asyncio.run(test_context_package_only(use_mock=args.mock))
    elif args.cypher_only:
        asyncio.run(test_cypher_tool_only(use_mock=args.mock))
    else:
        asyncio.run(test_v2_workflow(use_mock=args.mock))


if __name__ == "__main__":
    main()
