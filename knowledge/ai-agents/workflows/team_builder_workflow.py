"""Team Builder workflow for creating AI teams from intent and data scope."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.models.workflow_event import WorkflowEvent
from app.core.base_workflow import BaseWorkflow, WorkflowResult
from app.core.graphql_logger import ScenarioRunLogger
from app.config import Config

# Import team builder from theo module (for now, will be moved later)
from app.workflows.theo.team_builder import TeamBuilder
from app.workflows.theo.models import IntentPackage, Mission, TeamBuildingGuidance

logger = logging.getLogger(__name__)

# Import logfire if enabled
try:
    if Config.LOGFIRE_ENABLED:
        import logfire
    else:
        logfire = None
except Exception:
    logfire = None


class TeamBuilderWorkflow(BaseWorkflow):
    """Team Builder workflow for creating AI teams.

    This workflow:
    1. Accepts intent_package and data_scope as inputs
    2. Runs TeamBuilder to create the team (non-interactive)
    3. Emits team_building_progress and team_complete events
    4. Returns WorkflowResult with team configuration
    """

    def __init__(self):
        """Initialize Team Builder workflow."""
        super().__init__(
            workflow_id="team_builder",
            name="Team Builder Workflow"
        )

    async def execute(self, event: WorkflowEvent) -> WorkflowResult:
        """Execute the Team Builder workflow.

        Args:
            event: WorkflowEvent containing:
                - intent_package: Intent package from Theo or setup flow
                - data_scope: Data scope definition (optional)

        Returns:
            WorkflowResult with team configuration
        """
        start_time = datetime.utcnow()
        run_id = event.run_id
        tenant_id = event.tenant_id

        # Create Logfire span for entire Team Builder workflow
        span_ctx = None
        if logfire:
            span_ctx = logfire.span(
                'team_builder_workflow.execute',
                run_id=run_id,
                tenant_id=tenant_id,
                workspace_id=event.workspace_id,
                workflow_id=self.workflow_id,
            ).__enter__()

        logger.info(
            f"Starting Team Builder workflow for run_id={run_id}, "
            f"workspace_id={event.workspace_id}"
        )

        if logfire:
            logfire.info(
                'team_builder_workflow_started',
                run_id=run_id,
                workspace_id=event.workspace_id,
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

        try:
            # Extract inputs
            if not event.inputs_dict:
                raise ValueError("No inputs provided to Team Builder workflow")

            intent_package_dict = event.inputs_dict.get("intent_package")
            data_scope = event.inputs_dict.get("data_scope")

            if not intent_package_dict:
                raise ValueError("Missing required input: intent_package")

            # Convert dict to IntentPackage object
            intent_package = self._parse_intent_package(intent_package_dict)

            # Log workflow start
            if log_streamer:
                await log_streamer.log_event(
                    event_type="workflow_started",
                    message="Team Builder Workflow Started",
                    metadata={
                        "workspace_id": str(event.workspace_id),
                        "run_id": str(run_id),
                        "intent_title": intent_package.title
                    },
                    agent_id="theo"
                )

                # Emit team_building_progress event
                await log_streamer.log_event(
                    event_type="team_building_progress",
                    status="Starting team design process",
                    metadata={
                        "intent_title": intent_package.title,
                        "has_data_scope": data_scope is not None
                    }
                )

            # Log intent and data scope info
            logger.info(f"Building team for intent: {intent_package.title}")
            if data_scope:
                logger.info(f"Using data scope: {len(data_scope.get('scopes', []))} entities")

            # Emit progress update
            if log_streamer:
                await log_streamer.log_event(
                    event_type="team_building_progress",
                    status="Analyzing requirements and architecting team structure",
                    metadata={}
                )

            # Create team builder
            team_builder = TeamBuilder(
                workspace_id=event.workspace_id,
                tenant_id=event.tenant_id,
                graphql_endpoint=Config.GRAPHQL_ENDPOINT
            )

            # Build the team
            logger.info("Starting team building process")
            team_bundle = await team_builder.start_conversation(intent_package)

            if team_bundle is None:
                duration = (datetime.utcnow() - start_time).total_seconds()
                error_msg = "Team building failed"
                logger.error(error_msg)

                if log_streamer:
                    await log_streamer.log_event(
                        event_type="team_building_progress",
                        status="Team building failed",
                        metadata={"error": error_msg}
                    )

                if span_ctx:
                    span_ctx.set_attribute('success', False)
                    span_ctx.set_attribute('error', error_msg)

                return WorkflowResult(
                    run_id=run_id,
                    workflow_id=self.workflow_id,
                    success=False,
                    error=error_msg,
                    duration_seconds=duration,
                )

            logger.info(f"Team building complete: {team_bundle.team_name}")

            # Build team config for result
            conductor = team_bundle.team_definition.conductor
            specialists = team_bundle.team_definition.specialists

            team_config = {
                "team_id": team_bundle.team_name,
                "team_name": team_bundle.team_name,
                "conductor": {
                    "agent_id": self._make_agent_id(conductor.identity.role),
                    "name": conductor.identity.name,
                    "role": conductor.identity.role,
                    "capabilities": conductor.tools.available if conductor.tools.available else []
                },
                "agents": []
            }

            # Add conductor to agents list
            team_config["agents"].append({
                "agent_id": self._make_agent_id(conductor.identity.role),
                "name": conductor.identity.name,
                "role": conductor.identity.role,
                "type": "conductor",
                "capabilities": conductor.tools.available if conductor.tools.available else []
            })

            # Add specialists to agents list
            for specialist in specialists:
                agent_id = self._make_agent_id(specialist.identity.name)
                team_config["agents"].append({
                    "agent_id": agent_id,
                    "name": specialist.identity.name,
                    "role": specialist.identity.focus,
                    "type": "specialist",
                    "capabilities": specialist.tools.available if specialist.tools.available else []
                })

            # Emit team_complete event
            if log_streamer:
                await log_streamer.log_event(
                    event_type="team_complete",
                    team_config=team_config,
                    metadata={
                        "team_size": len(team_config["agents"]),
                        "specialist_count": len(specialists),
                        "tools_count": len(team_bundle.team_definition.get_all_tool_names())
                    }
                )

                await log_streamer.log_event(
                    event_type="workflow_stage_complete",
                    message="Team Created Successfully",
                    metadata={
                        "team_id": team_config['team_id'],
                        "conductor_name": conductor.identity.name,
                        "conductor_role": conductor.identity.role,
                        "specialist_count": len(specialists),
                        "total_agents": len(team_config['agents'])
                    },
                    agent_id="theo"
                )

            # Prepare result
            result_data = {
                "team_config": team_config,
                "team_location": f"teams/{team_bundle.team_name}",
                "intent_title": intent_package.title,
                "team_summary": f"{conductor.identity.name} ({conductor.identity.role}) with {len(specialists)} specialist(s)"
            }

            result_text = json.dumps(result_data, indent=2)
            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Team Builder workflow completed for run_id={run_id} in {duration:.2f}s")

            if logfire:
                logfire.info(
                    'team_builder_workflow_completed',
                    run_id=run_id,
                    duration_seconds=duration,
                    team_name=team_bundle.team_name,
                    specialist_count=len(specialists),
                    success=True,
                )
                if span_ctx:
                    span_ctx.set_attribute('success', True)
                    span_ctx.set_attribute('duration_seconds', duration)
                    span_ctx.set_attribute('team_name', team_bundle.team_name)
                    span_ctx.set_attribute('specialist_count', len(specialists))

            return WorkflowResult(
                run_id=run_id,
                workflow_id=self.workflow_id,
                success=True,
                result=result_text,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Team Builder workflow failed: {str(e)}"
            logger.exception(error_msg)

            if logfire:
                logfire.error(
                    'team_builder_workflow_failed',
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
                    event_type="team_building_progress",
                    status="Team building failed",
                    metadata={"error": error_msg}
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

    def _parse_intent_package(self, intent_dict: Dict[str, Any]) -> IntentPackage:
        """Parse intent package dictionary into IntentPackage object.

        Args:
            intent_dict: Dictionary containing intent package data

        Returns:
            IntentPackage object
        """
        # Parse mission
        mission_dict = intent_dict.get("mission", {})
        mission = Mission(
            objective=mission_dict.get("objective", ""),
            why=mission_dict.get("why", ""),
            success_looks_like=mission_dict.get("success_looks_like", "")
        )

        # Parse team guidance
        guidance_dict = intent_dict.get("team_guidance", {})
        team_guidance = TeamBuildingGuidance(
            expertise_needed=guidance_dict.get("expertise_needed", []),
            capabilities_needed=guidance_dict.get("capabilities_needed", []),
            complexity_notes=guidance_dict.get("complexity_notes", "")
        )

        # Create IntentPackage
        return IntentPackage(
            title=intent_dict.get("title", "Untitled Intent"),
            summary=intent_dict.get("summary", ""),
            mission=mission,
            team_guidance=team_guidance,
            conversation_transcript=intent_dict.get("conversation_transcript"),
            confirmed=intent_dict.get("confirmed", True)
        )

    def _make_agent_id(self, name: str) -> str:
        """Generate agent ID from name.

        Args:
            name: Agent name or role

        Returns:
            Sanitized agent ID
        """
        import re
        agent_id = name.lower()
        agent_id = re.sub(r'[^a-z0-9_-]+', '_', agent_id)
        agent_id = re.sub(r'_+', '_', agent_id).strip('_')
        return agent_id