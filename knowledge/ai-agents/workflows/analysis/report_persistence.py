"""Service for persisting analysis/scenario reports via GraphQL mutations."""

from typing import List, Dict, Any, Optional, TypeVar, Callable
import logging
import json
import asyncio
import random

from app.core.authenticated_graphql_client import run_graphql
from app.workflows.analysis.models import (
    AnalysisResult, ScenarioResult,
    ReportSectionOutput, ReportBlockOutput, SourceOutput,
    BlockType, DataGridContent, ComparisonTableContent
)

logger = logging.getLogger(__name__)

# Concurrency and retry configuration
MAX_CONCURRENT_GRAPHQL_REQUESTS = 5  # Limit concurrent requests to prevent SSL exhaustion
GRAPHQL_TIMEOUT_SECONDS = 30.0  # Increased timeout for report persistence
MAX_RETRY_ATTEMPTS = 2  # 1 retry after initial failure
INITIAL_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 10.0

# Global semaphore for rate limiting GraphQL requests
_graphql_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the global semaphore for rate limiting."""
    global _graphql_semaphore
    if _graphql_semaphore is None:
        _graphql_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GRAPHQL_REQUESTS)
    return _graphql_semaphore


T = TypeVar('T')


async def _run_graphql_with_retry(
    query: str,
    variables: Dict[str, Any],
    tenant_id: str,
    operation_name: str = "GraphQL operation"
) -> Dict[str, Any]:
    """
    Execute a GraphQL request with concurrency limiting, retry logic, and exponential backoff.

    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        tenant_id: Tenant ID for the request
        operation_name: Human-readable name for logging

    Returns:
        GraphQL response data

    Raises:
        RuntimeError: If all retry attempts fail
    """
    semaphore = _get_semaphore()
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        try:
            async with semaphore:
                result = await run_graphql(
                    query,
                    variables,
                    tenant_id=tenant_id,
                    timeout=GRAPHQL_TIMEOUT_SECONDS
                )
                return result
        except Exception as e:
            last_error = e
            error_msg = str(e)

            # Check if it's a retryable error (timeout, SSL, connection issues)
            is_retryable = any(keyword in error_msg.lower() for keyword in [
                "timeout", "ssl", "handshake", "connection", "urlopen error",
                "reset by peer", "errno 104", "errno 110", "temporarily unavailable"
            ])

            if not is_retryable or attempt == MAX_RETRY_ATTEMPTS:
                logger.error(
                    f"{operation_name} failed after {attempt} attempt(s): {error_msg}"
                )
                raise

            # Calculate delay with exponential backoff and jitter
            delay = min(
                INITIAL_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)),
                MAX_RETRY_DELAY_SECONDS
            )
            # Add jitter (±25%)
            delay = delay * (0.75 + random.random() * 0.5)

            logger.warning(
                f"{operation_name} failed (attempt {attempt}/{MAX_RETRY_ATTEMPTS}): {error_msg}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    raise RuntimeError(f"{operation_name} failed after {MAX_RETRY_ATTEMPTS} attempts: {last_error}")


class ReportPersistence:
    """Persist analysis and scenario results as Reports via GraphQL."""

    def __init__(self, workspace_id: str, tenant_id: str, scenario_id: Optional[str] = None, config=None):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.scenario_id = scenario_id  # Parent reference for reports
        self.config = config  # AnalysisWorkflowConfig for template settings

    async def create_workspace_analysis(
        self,
        title: str,
        description: Optional[str] = None
    ) -> str:
        """
        Create a WorkspaceAnalysis object to attach reports to.

        This is required to make reports visible in the workspace UI.

        Args:
            title: Title for the workspace analysis
            description: Body text for the workspace analysis card (optional)

        Returns:
            workspace_analysis_id (UUID string)
        """
        mutation = """
        mutation CreateWorkspaceAnalysis(
            $workspaceId: UUID!,
            $titleText: String!,
            $bodyText: String
        ) {
            createWorkspaceAnalysis(
                workspaceId: $workspaceId,
                titleText: $titleText,
                bodyText: $bodyText
            )
        }
        """

        variables = {
            "workspaceId": self.workspace_id,
            "titleText": title,
            "bodyText": description
        }

        result = await _run_graphql_with_retry(
            mutation, variables, tenant_id=self.tenant_id,
            operation_name="CreateWorkspaceAnalysis"
        )
        workspace_analysis_id = result.get("createWorkspaceAnalysis")

        if not workspace_analysis_id:
            raise RuntimeError(f"Failed to create WorkspaceAnalysis: {result}")

        logger.info(f"Created WorkspaceAnalysis: {workspace_analysis_id} for workspace {self.workspace_id}")
        return workspace_analysis_id

    async def create_scenario(
        self,
        title: str,
        description: Optional[str] = None,
        scenario_type: Optional[str] = None,
        parent_report_id: Optional[str] = None
    ) -> str:
        """
        Create a Scenario object to attach scenario reports to.

        This is required to make scenario reports visible and linked to their parent analysis.

        Args:
            title: Title for the scenario
            description: Description of the scenario (optional)
            scenario_type: Type of scenario (e.g., "what_if", "sensitivity_analysis") (optional)
            parent_report_id: Parent analysis report ID to link to (optional)

        Returns:
            scenario_id (UUID string)
        """
        mutation = """
        mutation CreateScenario(
            $workspaceId: UUID!,
            $name: String!,
            $createdBy: UUID!,
            $headerText: String,
            $mainText: String,
        ) {
            createScenario(
                workspaceId: $workspaceId,
                name: $name,
                createdBy: $createdBy,
                headerText: $headerText,
                mainText: $mainText
            )
        }
        """

        variables = {
            "workspaceId": self.workspace_id,
            "name": title,
            "createdBy": "470a99f7-0e67-4019-bbc1-027256b191c9",  # User ID,
            "headerText": scenario_type,
            "mainText": description
        }

        result = await _run_graphql_with_retry(
            mutation, variables, tenant_id=self.tenant_id,
            operation_name=f"CreateScenario({title})"
        )
        scenario_id = result.get("createScenario")

        logger.info(f"Created Scenario: {scenario_id} for workspace {self.workspace_id}")
        return scenario_id

    async def persist_analysis_report(
        self,
        result: AnalysisResult,
        workspace_analysis_id: Optional[str] = None
    ) -> str:
        """
        Persist an AnalysisResult as a Report.

        Args:
            result: The analysis result to persist
            workspace_analysis_id: Required - the WorkspaceAnalysis to attach this report to

        Returns: report_id
        """
        if not workspace_analysis_id:
            raise ValueError("workspace_analysis_id is required for analysis reports")

        # 1. Create Report attached to WorkspaceAnalysis
        report_id = await self._create_report(
            report_type="analysis",
            title=result.title,
            workspace_analysis_id=workspace_analysis_id,
            scenario_id=None  # Analysis reports use WorkspaceAnalysis, not Scenario
        )

        # 2. Create Sources first (need IDs for block references)
        source_id_map = await self._create_sources(report_id, result.sources)

        # 3. Create Sections and Blocks
        for section in result.sections:
            await self._create_section_with_blocks(report_id, section, source_id_map)

        # 4. Update status to completed
        await self._update_report_status(report_id, "completed")

        logger.info(f"Persisted analysis report {result.analysis_id} as Report {report_id}")
        return report_id

    async def persist_scenario_report(
        self,
        result: ScenarioResult,
        parent_report_id: str,
        scenario_id: Optional[str] = None
    ) -> str:
        """
        Persist a ScenarioResult as a Report linked to parent analysis.

        Args:
            result: The scenario execution result to persist
            parent_report_id: ID of the parent analysis report
            scenario_id: Optional scenario ID. If not provided, a new Scenario will be created.

        Returns: report_id
        """
        # Auto-create scenario if not provided or if it's a placeholder zeros UUID
        actual_scenario_id = scenario_id or self.scenario_id
        is_placeholder = actual_scenario_id in (None, "", "00000000-0000-0000-0000-000000000000")
        if is_placeholder:
            logger.info("Creating Scenario object...")
            actual_scenario_id = await self.create_scenario(
                title=result.title,
                description=result.description,
                scenario_type=result.scenario_type,
                parent_report_id=parent_report_id
            )
            logger.info(f"✓ Created Scenario: {actual_scenario_id}")

        # 1. Create Report (type="scenario") - use scenario_id as parent reference
        report_id = await self._create_report(
            report_type="scenario",
            title=result.title,
            scenario_id=actual_scenario_id,
            metadata=json.dumps({
                "parent_analysis": result.parent_analysis,
                "parent_report_id": parent_report_id,
                "scenario_type": result.scenario_type
            })
        )

        # 2. Create Sources
        source_id_map = await self._create_sources(report_id, result.sources)

        # 3. Create Sections and Blocks
        for section in result.sections:
            await self._create_section_with_blocks(report_id, section, source_id_map)

        # 4. Update status
        await self._update_report_status(report_id, "completed")

        logger.info(f"Persisted scenario report {result.scenario_id} as Report {report_id}")
        return report_id

    async def _create_report(
        self,
        report_type: str,
        title: str,
        workspace_analysis_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> str:
        """Create a Report and return its ID.

        Note: templateId and templateVersion are now optional (nullable).
        AI-generated reports don't use templates, so we pass None.

        IMPORTANT: Exactly one of workspaceAnalysisId or scenarioId must be provided.
        The GraphQL API requires a parent reference for every report.
        """
        # Build mutation and variables based on which parent ID is provided
        # The API requires exactly one of workspaceAnalysisId or scenarioId
        # Note: AI-generated reports don't use templates, so we omit templateId/templateVersion
        if workspace_analysis_id:
            mutation = """
            mutation CreateReport(
                $type: String!,
                $title: String!,
                $status: String!,
                $workspaceAnalysisId: UUID!,
                $metadata: String
            ) {
                createReport(
                    workspaceAnalysisId: $workspaceAnalysisId,
                    type: $type,
                    title: $title,
                    status: $status,
                    metadata: $metadata
                )
            }
            """
            variables = {
                "type": report_type,
                "title": title,
                "status": "draft",
                "workspaceAnalysisId": workspace_analysis_id,
                "metadata": metadata
            }
            parent_ref = f"workspace_analysis={workspace_analysis_id[:8]}"
        elif scenario_id:
            mutation = """
            mutation CreateReport(
                $type: String!,
                $title: String!,
                $status: String!,
                $scenarioId: UUID!,
                $metadata: String
            ) {
                createReport(
                    scenarioId: $scenarioId,
                    type: $type,
                    title: $title,
                    status: $status,
                    metadata: $metadata
                )
            }
            """
            variables = {
                "type": report_type,
                "title": title,
                "status": "draft",
                "scenarioId": scenario_id,
                "metadata": metadata
            }
            parent_ref = f"scenario={scenario_id[:8]}"
        else:
            raise ValueError("Either workspace_analysis_id or scenario_id must be provided to create a report")

        result = await _run_graphql_with_retry(
            mutation, variables, tenant_id=self.tenant_id,
            operation_name=f"CreateReport({title[:20]}, {parent_ref})"
        )
        return result.get("createReport")

    async def _create_sources(
        self,
        report_id: str,
        sources: List[SourceOutput]
    ) -> Dict[str, str]:
        """Create Sources and return mapping of temp_id -> real_id."""
        source_id_map = {}

        for source in sources:
            mutation = """
            mutation CreateSource(
                $reportId: UUID!,
                $sourceType: String!,
                $uri: String,
                $title: String,
                $description: String,
                $metadata: String
            ) {
                createSource(
                    reportId: $reportId,
                    sourceType: $sourceType,
                    uri: $uri,
                    title: $title,
                    description: $description,
                    metadata: $metadata
                )
            }
            """
            result = await _run_graphql_with_retry(
                mutation,
                {
                    "reportId": report_id,
                    "sourceType": source.source_type.value,
                    "uri": source.uri,
                    "title": source.title,
                    "description": source.description,
                    "metadata": json.dumps(source.metadata.model_dump()) if source.metadata else None
                },
                tenant_id=self.tenant_id,
                operation_name=f"CreateSource({source.title or source.source_id})"
            )
            real_id = result.get("createSource")
            source_id_map[source.source_id] = real_id

        return source_id_map

    async def _create_section_with_blocks(
        self,
        report_id: str,
        section: ReportSectionOutput,
        source_id_map: Dict[str, str]
    ):
        """Create a section and all its blocks."""
        # Create section
        section_mutation = """
        mutation CreateReportSection(
            $reportId: UUID!,
            $templateSectionId: UUID,
            $sectionType: String!,
            $header: String!,
            $order: Int!
        ) {
            createReportSection(
                reportId: $reportId,
                templateSectionId: $templateSectionId,
                sectionType: $sectionType,
                header: $header,
                order: $order
            )
        }
        """
        section_result = await _run_graphql_with_retry(
            section_mutation,
            {
                "reportId": report_id,
                "templateSectionId": None,
                "sectionType": section.section_type.value,
                "header": section.header,
                "order": section.order
            },
            tenant_id=self.tenant_id,
            operation_name=f"CreateReportSection({section.header})"
        )
        section_id = section_result.get("createReportSection")

        # Create blocks
        for block in section.blocks:
            # Map source refs to real IDs
            real_source_refs = [source_id_map.get(ref, ref) for ref in block.source_refs]

            await self._create_block(section_id, block, real_source_refs)

    def _convert_data_grid_to_markdown(self, content: DataGridContent) -> str:
        """Convert DataGridContent to markdown table format."""
        lines = []

        # Add title as H3 heading if present
        if content.title:
            lines.append(f"### {content.title}\n")

        # Build table header from column labels (ColumnDef is a Pydantic model)
        header_labels = [col.label or col.key for col in content.columns]
        lines.append("| " + " | ".join(header_labels) + " |")

        # Build separator row
        separators = ["-" * max(len(label), 3) for label in header_labels]
        lines.append("| " + " | ".join(separators) + " |")

        # Build data rows (TableRow has .values which is List[RowValue])
        for row in content.rows:
            # Build a lookup from column_key to value
            row_dict = {rv.column_key: rv.value for rv in row.values}
            cells = []
            for col in content.columns:
                value = row_dict.get(col.key, "")
                # Convert to string and escape pipe characters
                cell_value = str(value) if value is not None else ""
                cell_value = cell_value.replace("|", "\\|")
                cells.append(cell_value)
            lines.append("| " + " | ".join(cells) + " |")

        # Add summary as paragraph if present
        if content.summary:
            lines.append(f"\n{content.summary}")

        return "\n".join(lines)

    def _convert_comparison_table_to_markdown(self, content: ComparisonTableContent) -> str:
        """Convert ComparisonTableContent to markdown table format."""
        lines = []

        # Add title as H3 heading if present
        if content.title:
            lines.append(f"### {content.title}\n")

        # Build table header from column labels (ColumnDef is a Pydantic model)
        header_labels = [col.label or col.key for col in content.columns]
        lines.append("| " + " | ".join(header_labels) + " |")

        # Build separator row
        separators = ["-" * max(len(label), 3) for label in header_labels]
        lines.append("| " + " | ".join(separators) + " |")

        # Build data rows (TableRow has .values which is List[RowValue])
        for row in content.rows:
            # Build a lookup from column_key to value
            row_dict = {rv.column_key: rv.value for rv in row.values}
            cells = []
            for col in content.columns:
                value = row_dict.get(col.key, "")
                # Convert to string and escape pipe characters
                cell_value = str(value) if value is not None else ""
                cell_value = cell_value.replace("|", "\\|")
                cells.append(cell_value)
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    async def _create_block(
        self,
        section_id: str,
        block: ReportBlockOutput,
        source_refs: List[str]
    ):
        """Create a block and its content."""
        # Convert table block types to rich_text for DB storage
        # (DB doesn't support data_grid or comparison_table yet)
        actual_block_type = block.block_type
        if block.block_type in (BlockType.DATA_GRID, BlockType.COMPARISON_TABLE):
            actual_block_type = BlockType.RICH_TEXT

        # Create block shell
        block_mutation = """
        mutation CreateReportBlock(
            $sectionId: UUID!,
            $templateBlockId: UUID,
            $blockType: String!,
            $order: Int!,
            $sourceRefs: [String!],
            $layoutHints: String
        ) {
            createReportBlock(
                reportSectionId: $sectionId,
                templateBlockId: $templateBlockId,
                blockType: $blockType,
                order: $order,
                sourceRefs: $sourceRefs,
                layoutHints: $layoutHints
            )
        }
        """
        block_result = await _run_graphql_with_retry(
            block_mutation,
            {
                "sectionId": section_id,
                "templateBlockId": None,
                "blockType": actual_block_type.value,  # Use RICH_TEXT for tables
                "order": block.order,
                "sourceRefs": source_refs,
                "layoutHints": json.dumps(block.layout_hints.model_dump()) if block.layout_hints else None
            },
            tenant_id=self.tenant_id,
            operation_name=f"CreateReportBlock(order={block.order})"
        )
        block_id = block_result.get("createReportBlock")

        # Upsert content based on type
        await self._upsert_block_content(block_id, block)

    async def _upsert_block_content(self, block_id: str, block: ReportBlockOutput):
        """Upsert the appropriate content based on block type."""
        content = block.content

        if block.block_type == BlockType.RICH_TEXT:
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $content: String!) {
                    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
                }""",
                {"blockId": block_id, "content": content.markdown},
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockRichText"
            )

        elif block.block_type == BlockType.SINGLE_METRIC:
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $label: String!, $value: String!, $unit: String, $trend: String) {
                    upsertReportBlockSingleMetric(reportBlockId: $blockId, label: $label, value: $value, unit: $unit, trend: $trend)
                }""",
                {
                    "blockId": block_id,
                    "label": content.label,
                    "value": content.value,
                    "unit": content.unit,
                    "trend": content.trend
                },
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockSingleMetric"
            )

        elif block.block_type == BlockType.MULTI_METRIC:
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $metrics: String!) {
                    upsertReportBlockMultiMetric(reportBlockId: $blockId, metrics: $metrics)
                }""",
                {
                    "blockId": block_id,
                    "metrics": json.dumps([m.model_dump() for m in content.metrics])
                },
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockMultiMetric"
            )

        elif block.block_type == BlockType.INSIGHT_CARD:
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $title: String!, $body: String!, $badge: String, $severity: String) {
                    upsertReportBlockInsightCard(reportBlockId: $blockId, title: $title, body: $body, badge: $badge, severity: $severity)
                }""",
                {
                    "blockId": block_id,
                    "title": content.title,
                    "body": content.body,
                    "badge": content.badge,
                    "severity": content.severity
                },
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockInsightCard"
            )

        elif block.block_type == BlockType.DATA_GRID:
            # Convert to markdown and persist as rich_text
            markdown = self._convert_data_grid_to_markdown(content)
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $content: String!) {
                    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
                }""",
                {"blockId": block_id, "content": markdown},
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockDataGrid"
            )

        elif block.block_type == BlockType.COMPARISON_TABLE:
            # Convert to markdown and persist as rich_text
            markdown = self._convert_comparison_table_to_markdown(content)
            await _run_graphql_with_retry(
                """mutation($blockId: UUID!, $content: String!) {
                    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
                }""",
                {"blockId": block_id, "content": markdown},
                tenant_id=self.tenant_id,
                operation_name="UpsertBlockComparisonTable"
            )

    async def _update_report_status(self, report_id: str, status: str):
        """Update report status."""
        await _run_graphql_with_retry(
            """mutation($reportId: UUID!, $status: String!) {
                updateReport(reportId: $reportId, status: $status)
            }""",
            {"reportId": report_id, "status": status},
            tenant_id=self.tenant_id,
            operation_name=f"UpdateReportStatus({status})"
        )
