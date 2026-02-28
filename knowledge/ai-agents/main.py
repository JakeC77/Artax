"""Main application entry point for Azure Container App."""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Ensure package imports work (adds package root to sys.path)
# This is done automatically when package is imported, but for direct script execution:
if __name__ == "__main__":
    # Add package root to path for imports
    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))

from app.config import Config
from app.core.workflow_registry import WorkflowRegistry
from app.core.workflow_router import WorkflowRouter
from app.services.service_bus_handler import create_handler

# Optional: FastAPI for health check endpoint
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Silence Azure Identity verbose logging
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


async def initialize_router() -> WorkflowRouter:
    """Initialize WorkflowRouter with registered workflows."""
    logger.info("Initializing WorkflowRouter...")
    
    # Create registry
    registry = WorkflowRegistry()
    
    # Load workflows from directory (placeholder for future YAML-based loading)
    registry.load_from_directory(Config.WORKFLOW_DIRECTORY)
    
    # Register workspace-chat workflow
    try:
        from app.workflows.workspace_chat import WorkspaceChatWorkflow
        from app.core.registry import AgentRegistry
        from pathlib import Path
        
        # Initialize tool registry (import tools to auto-register them)
        try:
            from app.tools import TOOL_REGISTRY
            tool_registry = TOOL_REGISTRY
            logger.info(f"Initialized tool registry with {len(tool_registry)} tools: {', '.join(tool_registry.keys())}")
        except ImportError as e:
            logger.warning(f"Failed to import tools: {e}. Agents will not have access to tools.")
            tool_registry = {}
        
        # Initialize agent registry (required for workspace-chat)
        agent_registry = AgentRegistry()
        
        # Try to load agents from directory (optional - workflow can work without agents for quick answers)
        agent_directory = Path(__file__).parent / "agents"
        if agent_directory.exists():
            try:
                agent_registry.load_from_directory(agent_directory)
                logger.info(f"Loaded agents: {', '.join(agent_registry.agent_ids())}")
            except Exception as e:
                logger.warning(f"Failed to load agents: {e}. Workspace chat will work for quick answers only.")
        else:
            logger.warning(f"Agent directory not found: {agent_directory}. Workspace chat will work for quick answers only.")
        
        # Create workspace chat workflow with tool registry
        workspace_chat = WorkspaceChatWorkflow(agent_registry=agent_registry, tool_registry=tool_registry)
        registry.register(workspace_chat)
        logger.info("Registered workspace-chat workflow")
    except Exception as e:
        logger.warning(f"Failed to register workspace-chat workflow: {e}")
    
    # Register example workflow
    try:
        from app.workflows.example_workflow import ExampleWorkflow
        example_workflow = ExampleWorkflow()
        registry.register(example_workflow)
        logger.info("Registered example workflow")
    except Exception as e:
        logger.warning(f"Failed to register example workflow: {e}")
    
    # Register theo workflow
    try:
        from app.workflows.theo_workflow import TheoWorkflow
        theo_workflow = TheoWorkflow()
        registry.register(theo_workflow)
        logger.info("Registered theo workflow")
    except Exception as e:
        logger.warning(f"Failed to register theo workflow: {e}")

    # Register data recommender workflow
    try:
        from app.workflows.data_recommender_workflow import DataRecommenderWorkflow
        data_recommender_workflow = DataRecommenderWorkflow()
        registry.register(data_recommender_workflow)
        logger.info("Registered data_recommender workflow")
    except Exception as e:
        logger.warning(f"Failed to register data_recommender workflow: {e}")

    # Register data recommender execution workflow
    try:
        from app.workflows.data_recommender_execution_workflow import DataRecommenderExecutionWorkflow
        data_recommender_execution_workflow = DataRecommenderExecutionWorkflow()
        registry.register(data_recommender_execution_workflow)
        logger.info("Registered data_recommender_execution workflow")
    except Exception as e:
        logger.warning(f"Failed to register data_recommender_execution workflow: {e}")

    # Register team builder workflow
    try:
        from app.workflows.team_builder_workflow import TeamBuilderWorkflow
        team_builder_workflow = TeamBuilderWorkflow()
        registry.register(team_builder_workflow)
        logger.info("Registered team_builder workflow")
    except Exception as e:
        logger.warning(f"Failed to register team_builder workflow: {e}")

    # Register unified workspace setup workflow
    try:
        from app.workflows.workspace_setup_workflow import WorkspaceSetupWorkflow
        workspace_setup_workflow = WorkspaceSetupWorkflow()
        registry.register(workspace_setup_workflow)
        logger.info("Registered workspace_setup workflow")
    except Exception as e:
        logger.warning(f"Failed to register workspace_setup workflow: {e}")

    # Register analysis workflow
    try:
        from app.workflows.analysis_workflow import AnalysisWorkflow
        analysis_workflow = AnalysisWorkflow()
        registry.register(analysis_workflow)
        logger.info("Registered analysis_workflow workflow")
    except Exception as e:
        logger.warning(f"Failed to register analysis_workflow workflow: {e}")

    # Register document-graphiti workflow (same event shape; route by workflowId "document-graphiti")
    # Chained: after Graphiti ingest, runs entity resolution and writes entity_resolution.json
    try:
        from app.workflows.document_indexing import DocumentGraphitiWorkflow
        document_graphiti_workflow = DocumentGraphitiWorkflow()
        registry.register(document_graphiti_workflow)
        logger.info("Registered document-graphiti workflow")
    except Exception as e:
        logger.warning(f"Failed to register document-graphiti workflow: {e}")

    # Register entity-resolution workflow (re-run resolution only; expects Graphiti to have run)
    try:
        from app.workflows.document_indexing import EntityResolutionWorkflow
        entity_resolution_workflow = EntityResolutionWorkflow()
        registry.register(entity_resolution_workflow)
        logger.info("Registered entity-resolution workflow")
    except Exception as e:
        logger.warning(f"Failed to register entity-resolution workflow: {e}")

    # Register ontology creation workflow
    try:
        from app.workflows.ontology_creation_workflow import OntologyCreationWorkflow
        ontology_creation_workflow = OntologyCreationWorkflow()
        registry.register(ontology_creation_workflow)
        logger.info("Registered ontology-creation workflow")
    except Exception as e:
        logger.warning(f"Failed to register ontology-creation workflow: {e}")

    # Register ontology conversation workflow (never-ending, resumable, DB-aware chat)
    try:
        from app.workflows.ontology_conversation_workflow import OntologyConversationWorkflow
        ontology_conversation_workflow = OntologyConversationWorkflow()
        registry.register(ontology_conversation_workflow)
        logger.info("Registered ontology-conversation workflow")
    except Exception as e:
        logger.warning(f"Failed to register ontology-conversation workflow: {e}")

    # Register data loading workflow
    try:
        from app.workflows.data_loading import DataLoadingWorkflow
        data_loading_workflow = DataLoadingWorkflow()
        registry.register(data_loading_workflow)
        logger.info("Registered data-loading workflow")
    except Exception as e:
        logger.error(f"Failed to register data-loading workflow: {e}", exc_info=True)

    workflow_ids = registry.workflow_ids()
    logger.info(f"Loaded {len(workflow_ids)} workflows: {', '.join(workflow_ids) if workflow_ids else 'none'}")
    
    # Create router
    router = WorkflowRouter(registry)
    logger.info("WorkflowRouter created")
    
    return router


def setup_logfire():
    """Configure Logfire observability with graceful degradation."""
    if not Config.LOGFIRE_ENABLED:
        logger.info("Logfire observability disabled (LOGFIRE_ENABLED=false)")
        return

    try:
        import logfire
        from pathlib import Path

        # Find .logfire directory in repo root
        # From app/main.py, go up 1 level to repo root
        repo_root = Path(__file__).resolve().parent.parent
        logfire_dir = repo_root / ".logfire"

        logfire.configure(
            token=Config.LOGFIRE_TOKEN,  # Falls back to .logfire/ if None
            service_name=Config.LOGFIRE_SERVICE_NAME,
            environment=Config.ENVIRONMENT,
            send_to_logfire='if-token-present',  # Graceful: only send if token present
            config_dir=logfire_dir if logfire_dir.exists() else None,
        )

        # Instrument Pydantic AI agents (captures prompts, completions, tool calls)
        logfire.instrument_pydantic_ai()

        logger.info(
            f"Logfire observability enabled "
            f"(environment={Config.ENVIRONMENT}, service={Config.LOGFIRE_SERVICE_NAME})"
        )

    except Exception as e:
        # CRITICAL: Don't crash if Logfire fails - just log warning
        logger.warning(
            f"Failed to initialize Logfire observability: {e}. "
            "Continuing without observability. "
            "Set LOGFIRE_ENABLED=false to suppress this warning."
        )


async def main():
    """Main application entry point."""
    setup_logging()

    logger.info("=" * 70)
    logger.info("GEODESIC AI - MULTI-WORKFLOW SERVICE")
    logger.info("=" * 70)

    # Initialize Logfire observability (with graceful degradation)
    setup_logfire()

    # Validate configuration
    missing = Config.validate()
    if missing:
        logger.error(f"Missing required configuration: {', '.join(missing)}")
        sys.exit(1)
    
    logger.info("Configuration validated")
    logger.info(f"Config summary: {Config.get_summary()}")
    
    # Log Service Bus configuration before connecting
    logger.info("Service Bus Configuration:")
    logger.info(f"  Queue Name: {Config.SERVICE_BUS_QUEUE_NAME}")
    logger.info(f"  Connection String Set: {'Yes' if Config.SERVICE_BUS_CONNECTION_STRING else 'No'}")
    logger.info(f"  Max Concurrent Messages: {Config.MAX_CONCURRENT_MESSAGES}")
    logger.info(f"  Max Lock Duration: {Config.SERVICE_BUS_MAX_LOCK_DURATION_SECONDS}s")
    logger.info(f"  Lock Renewal Interval: {Config.SERVICE_BUS_LOCK_RENEWAL_INTERVAL_SECONDS}s")
    
    # Initialize router
    router = await initialize_router()
    
    # Create Service Bus handler
    handler = await create_handler(router)
    await handler.start()
    logger.info("Service Bus handler started")
    
    # Setup health check endpoint (for Container App monitoring)
    health_app = None
    health_task = None

    if FASTAPI_AVAILABLE:
        health_app = FastAPI(
            title="Geodesic AI - Health Check",
            description="Health check endpoint for production monitoring",
            version="1.0.0",
        )

        @health_app.get("/health")
        async def health_check():
            metrics = router.get_metrics()

            # Include conversation metrics
            try:
                from app.core.conversation_metrics import ConversationMetrics
                conversation_metrics = ConversationMetrics.get_metrics()
            except Exception as e:
                conversation_metrics = {"error": str(e)}

            # Include connection pool metrics
            try:
                from app.core.connection_pool import get_connection_pool
                pool = get_connection_pool()
                connection_metrics = {
                    "active_connections": pool.get_active_connections(),
                    "available_slots": pool.get_available_slots(),
                    "max_connections": pool.max_connections,
                }
            except Exception as e:
                connection_metrics = {"error": str(e)}

            return JSONResponse({
                "status": "healthy",
                "service": "multi-workflow",
                "timestamp": asyncio.get_event_loop().time(),
                "workflows_registered": router.registry.count(),
                "routing_metrics": metrics,
                "conversation_metrics": conversation_metrics,
                "connection_metrics": connection_metrics,
            })
        
        # Run health check server in background
        config = uvicorn.Config(
            health_app,
            host="0.0.0.0",
            port=Config.HEALTH_CHECK_PORT,
            log_level=Config.LOG_LEVEL.lower(),
        )
        server = uvicorn.Server(config)
        health_task = asyncio.create_task(server.serve())
        logger.info(f"Health check endpoint started on port {Config.HEALTH_CHECK_PORT}")
    
    # Setup graceful shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()
    
    # Register signal handlers
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Start listening (this blocks)
        logger.info("Starting message listener...")
        listener_task = asyncio.create_task(handler.listen())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        logger.info("Shutting down...")
        
        # Cancel listener
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        
        # Stop handler
        await handler.stop()
        
        # Stop health check server
        if health_task:
            health_task.cancel()
            try:
                await health_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Shutdown complete")
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        signal_handler()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


