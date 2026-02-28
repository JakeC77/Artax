"""Data loading workflow for loading CSV data into graph database."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
import uuid

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.event_stream_reader import EventStreamReader
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config

# Import data loading modules
from app.workflows.data_loading.data_loader_agent import create_data_loader_agent
from app.workflows.data_loading.models import DataLoadingState
from app.workflows.data_loading.csv_parser import parse_csv_from_blob, parse_csv
from app.utils.streaming import stream_agent_text
from uuid import uuid4

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class DataLoadingWorkflow(BaseWorkflow):
    """Data loading workflow for loading CSV data into graph database.
    
    This workflow:
    1. Uses EventStreamReader to read user messages during data loading
    2. Runs DataLoaderAgent in conversational mode with event stream support
    3. Analyzes CSV structure
    4. Maps CSV columns to ontology entities/fields
    5. Validates mapping
    6. Inserts data into graph database
    7. Emits progress events during insertion
    """
    
    def __init__(self):
        """Initialize data loading workflow."""
        super().__init__(
            workflow_id="data-loading",
            name="Data Loading Workflow"
        )
    
    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the data loading workflow.

        Args:
            event: WorkflowEvent containing all event data

        Returns:
            WorkflowResult with execution details
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id
        workspace_id = event.workspace_id

        # Create Logfire span for entire workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'data_loading_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting data loading workflow for run_id={run_id}, "
            f"workspace_id={workspace_id}"
        )

        if logfire:
            logfire.info(
                'data_loading_workflow_started',
                run_id=run_id,
                workspace_id=workspace_id,
            )
        
        # Initialize GraphQL logger
        log_streamer = None
        if Config.GRAPHQL_LOGGING_ENABLED:
            try:
                log_streamer = ScenarioRunLogger(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    enabled=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize GraphQL logger: {e}")
        
        # Initialize event stream reader (required for conversational workflow)
        event_reader = None
        try:
            event_reader = EventStreamReader(
                run_id=run_id,
                tenant_id=tenant_id,
                graphql_endpoint=Config.GRAPHQL_ENDPOINT,
            )
            await event_reader.start()
            logger.info("Event stream reader started")
        except Exception as e:
            logger.error(f"Failed to start event stream reader: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            if span_ctx:
                span_ctx.set_attribute('success', False)
                span_ctx.set_attribute('error', f"Failed to start event stream: {str(e)}")
                span_ctx.__exit__(None, None, None)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=f"Failed to start event stream: {str(e)}",
                duration_seconds=duration,
            )
        
        try:
            # Log workflow start
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Data Loading Workflow Started",
                    metadata={
                        "workspace_id": str(workspace_id),
                        "run_id": str(run_id),
                        "stage": "data_loading"
                    },
                    agent_id="data_loader_agent"
                )
            
            # Extract inputs from event
            csv_path = None
            csv_content = None
            ontology_id = None
            initial_instructions = None
            
            if event.inputs_dict:
                csv_path = event.inputs_dict.get("csv_path")
                csv_content_str = event.inputs_dict.get("csv_content")
                ontology_id = event.inputs_dict.get("ontology_id")
                initial_instructions = event.inputs_dict.get("initial_instructions")
                
                # Decode CSV content if provided as base64 or string
                if csv_content_str:
                    try:
                        import base64
                        csv_content = base64.b64decode(csv_content_str)
                    except Exception:
                        # Try as plain string
                        csv_content = csv_content_str.encode('utf-8') if isinstance(csv_content_str, str) else csv_content_str
            
            if not initial_instructions and event.prompt:
                initial_instructions = event.prompt
            
            # Fetch per-ontology Neo4j connection details if available
            neo4j_connection = None
            if ontology_id:
                try:
                    from app.workflows.data_loading.neo4j_connection import get_ontology_neo4j_connection
                    neo4j_connection = await get_ontology_neo4j_connection(ontology_id, tenant_id)
                    if neo4j_connection:
                        logger.info(f"Using per-ontology Neo4j connection for ontology {ontology_id}")
                    else:
                        logger.info(f"No per-ontology Neo4j configured for ontology {ontology_id}, using default")
                except Exception as e:
                    logger.warning(f"Failed to fetch per-ontology Neo4j connection: {e}. Using default Neo4j config.")
            
            # Create data loading state
            state = DataLoadingState()
            state.started_at = datetime.utcnow()
            state.ontology_id = ontology_id
            
            # Create agent
            logger.info("Starting data loading phase")
            loading_start_time = datetime.utcnow()

            loading_span = None
            if logfire:
                loading_span = logfire.span(
                    'data_loading_workflow.data_loading',
                    run_id=run_id,
                    has_csv_path=csv_path is not None,
                    has_csv_content=csv_content is not None,
                    ontology_id=ontology_id,
                ).__enter__()

            try:
                agent = create_data_loader_agent()
                
                # Prepare agent context
                agent_deps = {
                    "tenant_id": tenant_id,
                    "workspace_id": workspace_id,
                    "state": state,
                    "csv_path": csv_path,
                    "csv_content": csv_content,
                    "ontology_id": ontology_id,
                    "neo4j_connection": neo4j_connection,  # Per-ontology connection details or None
                }
                
                # Get blob service if needed
                if csv_path:
                    try:
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
                                blob_service = None
                        agent_deps["blob_service"] = blob_service
                    except Exception as e:
                        logger.warning(f"Failed to create blob service: {e}")
                
                # Start conversation with agent
                initial_prompt = (
                    f"I need to load CSV data into the graph database. "
                    f"{'Instructions: ' + initial_instructions if initial_instructions else 'Please analyze the CSV and map it to the ontology.'}"
                )
                
                if csv_path:
                    initial_prompt += f"\n\nCSV file path: {csv_path}"
                elif csv_content:
                    initial_prompt += "\n\nCSV content is provided."
                else:
                    initial_prompt += "\n\nPlease wait for CSV file to be uploaded."
                
                # Run agent in conversational mode
                message_history = []
                exchange_count = 0
                workflow_complete = False
                
                # First, analyze CSV if provided
                if csv_path or csv_content:
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="agent_message",
                            message="Analyzing CSV structure...",
                            agent_id="data_loader_agent",
                        )
                    
                    # Agent will call analyze_csv_structure tool
                    result = await agent.run(
                        initial_prompt,
                        deps=agent_deps
                    )
                    message_history.extend(result.new_messages())
                    
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="agent_message",
                            message=result.output,
                            agent_id="data_loader_agent",
                        )
                    
                    # Check if CSV was analyzed
                    csv_structure = agent_deps.get("csv_structure")
                    if csv_structure and log_streamer:
                        await log_streamer.log_event(
                            event_type="csv_analyzed",
                            message="CSV structure analyzed",
                            metadata={
                                "columns": [
                                    {
                                        "name": col.name,
                                        "data_type": col.data_type,
                                        "sample_values": col.sample_values[:3],
                                        "nullable": col.nullable
                                    }
                                    for col in csv_structure.columns
                                ],
                                "row_count": csv_structure.row_count,
                                "has_headers": csv_structure.has_headers
                            },
                            agent_id="data_loader_agent",
                        )
                
                # Conversation loop - wait for user messages and process
                while not workflow_complete:
                    # Get next user message or control event
                    user_input, event_type, event_metadata = await self._get_next_user_message(
                        event_reader,
                        timeout=300.0
                    )
                    
                    if event_type == "quit" or event_type == "timeout":
                        logger.info("User quit or timeout")
                        break
                    
                    if event_type == "empty" or not user_input:
                        continue
                    
                    # Process user message
                    try:
                        exchange_count += 1
                        
                        # Stream agent response
                        result = None
                        agent_output = ""
                        if log_streamer:
                            # Stream with logging
                            message_id = str(uuid4())
                            
                            async def on_batch(batch_text: str, acc_len: int, part_idx, metadata: dict):
                                await log_streamer.log_event(
                                    event_type="agent_message",
                                    message=batch_text,
                                    agent_id="data_loader_agent",
                                    metadata=metadata
                                )
                            
                            async for batch_text, acc_len, part_idx, metadata, event_result in stream_agent_text(
                                agent,
                                user_input,
                                deps=agent_deps,
                                message_history=message_history,
                                on_batch=on_batch,
                                batch_size=30,
                                flush_interval=0.05,
                                track_full_text=True,
                                message_id=message_id,
                            ):
                                if batch_text:
                                    agent_output += batch_text
                                if event_result is not None:
                                    result = event_result
                            
                            # Fallback to non-streaming if no result from stream
                            if result is None:
                                result = await agent.run(
                                    user_input,
                                    deps=agent_deps,
                                    message_history=message_history
                                )
                                agent_output = result.output
                                # Log the complete message if we had to fall back
                                await log_streamer.log_event(
                                    event_type="agent_message",
                                    message=agent_output,
                                    agent_id="data_loader_agent",
                                    metadata={"completed": True, "buffered": True}
                                )
                        else:
                            # No log_streamer - use non-streaming
                            result = await agent.run(
                                user_input,
                                deps=agent_deps,
                                message_history=message_history
                            )
                            agent_output = result.output
                        
                        # Extend message history from result
                        if result:
                            message_history.extend(result.new_messages())
                        
                        # Check for mapping proposed
                        mapping = agent_deps.get("mapping")
                        if mapping and log_streamer:
                            # Emit mapping_proposed event (only once)
                            if not agent_deps.get("mapping_proposed_emitted"):
                                await log_streamer.log_event(
                                    event_type="mapping_proposed",
                                    message="I'm proposing this mapping—does it look correct?",
                                    metadata={
                                        "entity_mappings": [
                                            {
                                                "entity_name": em.entity_name,
                                                "csv_columns": em.csv_columns,
                                                "field_mappings": [
                                                    {
                                                        "csv_column": fm.csv_column,
                                                        "field_name": fm.field_name,
                                                        "is_identifier": fm.is_identifier
                                                    }
                                                    for fm in em.field_mappings
                                                ]
                                            }
                                            for em in mapping.entity_mappings
                                        ],
                                        "relationship_mappings": [
                                            {
                                                "relationship_type": rm.relationship_type,
                                                "from_entity": rm.from_entity,
                                                "to_entity": rm.to_entity,
                                                "csv_columns": rm.csv_columns
                                            }
                                            for rm in mapping.relationship_mappings
                                        ],
                                        "unmapped_columns": mapping.unmapped_columns
                                    },
                                    agent_id="data_loader_agent",
                                )
                                agent_deps["mapping_proposed_emitted"] = True
                        
                        # Check for validation result
                        validation_result = agent_deps.get("validation_result")
                        if validation_result and log_streamer and not agent_deps.get("validation_emitted"):
                            await log_streamer.log_event(
                                event_type="mapping_validated",
                                message=validation_result.summary,
                                metadata={
                                    "is_valid": validation_result.is_valid,
                                    "errors": [
                                        {
                                            "type": e.error_type,
                                            "message": e.message,
                                            "row": e.row_number,
                                            "column": e.column_name
                                        }
                                        for e in validation_result.errors
                                    ],
                                    "warnings": [
                                        {
                                            "type": w.error_type,
                                            "message": w.message,
                                            "row": w.row_number,
                                            "column": w.column_name
                                        }
                                        for w in validation_result.warnings
                                    ],
                                    "summary": validation_result.summary
                                },
                                agent_id="data_loader_agent",
                            )
                            agent_deps["validation_emitted"] = True
                        
                        # Check for preview
                        preview = agent_deps.get("preview")
                        if preview and log_streamer and not agent_deps.get("preview_emitted"):
                            await log_streamer.log_event(
                                event_type="insertion_preview",
                                message="Preview of what will be inserted",
                                metadata={
                                    "nodes_to_create": preview.nodes_to_create,
                                    "relationships_to_create": preview.relationships_to_create,
                                    "sample_nodes": {k: v[:3] for k, v in preview.sample_nodes.items()},
                                    "sample_relationships": preview.sample_relationships[:5],
                                    "total_rows": len(agent_deps.get("csv_rows", []))
                                },
                                agent_id="data_loader_agent",
                            )
                            agent_deps["preview_emitted"] = True
                        
                        # Check for node creation progress
                        if state.nodes_created > 0 and log_streamer:
                            last_emitted_nodes = agent_deps.get("last_emitted_nodes", 0)
                            if state.nodes_created > last_emitted_nodes:
                                await log_streamer.log_event(
                                    event_type="nodes_created",
                                    message=f"Created {state.nodes_created} nodes",
                                    metadata={
                                        "created": state.nodes_created,
                                        "total": len(agent_deps.get("csv_rows", []))
                                    },
                                    agent_id="data_loader_agent",
                                )
                                agent_deps["last_emitted_nodes"] = state.nodes_created
                        
                        # Check for relationship creation progress
                        if state.relationships_created > 0 and log_streamer:
                            last_emitted_rels = agent_deps.get("last_emitted_relationships", 0)
                            if state.relationships_created > last_emitted_rels:
                                await log_streamer.log_event(
                                    event_type="relationships_created",
                                    message=f"Created {state.relationships_created} relationships",
                                    metadata={
                                        "created": state.relationships_created
                                    },
                                    agent_id="data_loader_agent",
                                )
                                agent_deps["last_emitted_relationships"] = state.relationships_created
                        
                        # Don't auto-complete - let conversation continue so user can make adjustments
                        # Workflow only completes when user explicitly quits or times out
                            
                    except Exception as e:
                        logger.exception(f"Error processing user message: {e}")
                        if log_streamer:
                            await log_streamer.log_event(
                                event_type="workflow_error",
                                message=f"Error: {str(e)}",
                                agent_id="data_loader_agent",
                            )
                
                loading_duration = (datetime.utcnow() - loading_start_time).total_seconds()

                if loading_span:
                    loading_span.set_attribute('nodes_created', state.nodes_created)
                    loading_span.set_attribute('relationships_created', state.relationships_created)
                    loading_span.set_attribute('duration_seconds', loading_duration)
            finally:
                if loading_span:
                    loading_span.__exit__(None, None, None)
            
            # Mark completion
            state.completed_at = datetime.utcnow()
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_complete",
                    message=f"Data loading complete: {state.nodes_created} nodes, {state.relationships_created} relationships created",
                    agent_id="data_loader_agent",
                )

            logger.info(f"Data loading workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'data_loading_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    nodes_created=state.nodes_created,
                    relationships_created=state.relationships_created,
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('nodes_created', state.nodes_created)
                    span_ctx.set_attribute('relationships_created', state.relationships_created)

            # Build result
            result_data = {
                "nodes_created": state.nodes_created,
                "relationships_created": state.relationships_created,
                "errors": state.errors,
                "completed": True
            }

            result_text = json.dumps(result_data, indent=2)

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Data loading workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'data_loading_workflow_failed',
                    run_id=run_id,
                    error=error_msg,
                    error_type=type(e).__name__,
                    duration_seconds=duration,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', False)
                    span_ctx.set_attribute('error', error_msg)
                    span_ctx.record_exception(e)

            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_error",
                    message=error_msg,
                    agent_id="data_loader_agent",
                )

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=False,
                error=error_msg,
                duration_seconds=duration,
            )

        finally:
            # Close Logfire span
            if span_ctx:
                span_ctx.__exit__(None, None, None)

            # Clean up event stream reader
            if event_reader:
                try:
                    await event_reader.stop()
                    logger.info("Event stream reader stopped")
                except Exception as e:
                    logger.warning(f"Error stopping event stream reader: {e}")
    
    async def _get_next_user_message(
        self,
        message_source: EventStreamReader,
        timeout: Optional[float] = None
    ) -> tuple[Optional[str], str, Optional[dict]]:
        """
        Get next user message or control event from event stream.
        
        Returns:
            Tuple of (message, event_type, metadata)
        """
        try:
            event = await message_source.wait_for_event(
                event_type=["user_message", "confirm_mapping", "confirm_insertion", "reject_mapping"],
                timeout=timeout
            )
            
            if event:
                event_type = event.get("event_type", "user_message")
                metadata = event.get("metadata", {})
                
                if event_type in ["confirm_mapping", "confirm_insertion"]:
                    return ("yes", "user_message", metadata)
                elif event_type == "reject_mapping":
                    feedback = metadata.get("feedback", "Please revise the mapping")
                    return (feedback, "user_message", metadata)
                
                # Regular user message
                user_message = event.get("message", "").strip()
                if user_message.lower() in ['quit', 'exit']:
                    return None, "quit", None
                return (user_message, "user_message", metadata) if user_message else (None, "empty", None)
            else:
                # Timeout
                return None, "timeout", None
        except Exception as e:
            logger.error(f"Error reading from event stream: {e}")
            return None, "quit", None
