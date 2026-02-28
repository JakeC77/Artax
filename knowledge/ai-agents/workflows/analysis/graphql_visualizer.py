"""
GraphQL Mutation Visualizer for Report Persistence.

This module provides detailed visualization of GraphQL mutations that will be
executed when posting analysis reports to the database. Useful for debugging
and understanding the exact database operations.
"""

import json
from typing import List, Dict, Any, Optional
from app.workflows.analysis.models import (
    AnalysisResult, ScenarioResult,
    ReportSectionOutput, ReportBlockOutput,
    SourceOutput, BlockType, DataGridContent, ComparisonTableContent
)


class GraphQLMutationVisualizer:
    """Visualize GraphQL mutations for report persistence."""

    def __init__(self, workspace_id: str, tenant_id: str, scenario_id: Optional[str], config=None):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.scenario_id = scenario_id
        self.config = config
        self.mutation_count = 0

    def visualize_analysis_report(
        self,
        result: AnalysisResult,
        create_workspace_analysis: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate list of all GraphQL mutations for an analysis report.

        Args:
            result: The analysis result to visualize
            create_workspace_analysis: If True, include createWorkspaceAnalysis mutation

        Returns:
            List of mutation objects with operation name, query, variables, and description
        """
        mutations = []
        self.mutation_count = 0

        # 0. Create WorkspaceAnalysis if needed
        if create_workspace_analysis:
            workspace_analysis_mutation = self._create_workspace_analysis_mutation(result)
            mutations.append(workspace_analysis_mutation)

        # 1. Create Report
        report_mutation = self._create_report_mutation(result)
        mutations.append(report_mutation)
        report_id = "<generated-report-id>"

        # 2. Create Sources
        source_id_map = {}
        for i, source in enumerate(result.sources):
            source_mutation = self._create_source_mutation(report_id, source, i + 1)
            mutations.append(source_mutation)
            source_id_map[source.source_id] = f"<generated-source-{i+1}>"

        # 3. Create Sections and Blocks
        for section_idx, section in enumerate(result.sections):
            section_mutations = self._create_section_with_blocks(
                report_id, section, source_id_map, section_idx + 1
            )
            mutations.extend(section_mutations)

        # 4. Update Report Status
        status_mutation = self._update_report_status_mutation(report_id, "completed")
        mutations.append(status_mutation)

        return mutations

    def visualize_scenario_report(
        self,
        result: ScenarioResult,
        parent_report_id: str
    ) -> List[Dict[str, Any]]:
        """
        Generate list of all GraphQL mutations for a scenario report.

        Returns:
            List of mutation objects
        """
        mutations = []
        self.mutation_count = 0

        # 1. Create Report (with parent reference)
        report_mutation = self._create_scenario_report_mutation(result, parent_report_id)
        mutations.append(report_mutation)
        report_id = "<generated-report-id>"

        # 2. Create Sources
        source_id_map = {}
        for i, source in enumerate(result.sources):
            source_mutation = self._create_source_mutation(report_id, source, i + 1)
            mutations.append(source_mutation)
            source_id_map[source.source_id] = f"<generated-source-{i+1}>"

        # 3. Create Sections and Blocks
        for section_idx, section in enumerate(result.sections):
            section_mutations = self._create_section_with_blocks(
                report_id, section, source_id_map, section_idx + 1
            )
            mutations.extend(section_mutations)

        # 4. Update Status
        status_mutation = self._update_report_status_mutation(report_id, "completed")
        mutations.append(status_mutation)

        return mutations

    def _create_workspace_analysis_mutation(self, result: AnalysisResult) -> Dict[str, Any]:
        """Generate createWorkspaceAnalysis mutation."""
        self.mutation_count += 1

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
            "titleText": result.title,
            "bodyText": result.description
        }

        return {
            "operation": f"#{self.mutation_count} CREATE_WORKSPACE_ANALYSIS",
            "description": f"Create workspace analysis container: {result.title}",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "UUID (workspace_analysis_id)"
        }

    def _create_report_mutation(self, result: AnalysisResult) -> Dict[str, Any]:
        """Generate createReport mutation for analysis."""
        self.mutation_count += 1

        ai_template_id = self.config.template_id if self.config and hasattr(self.config, 'template_id') else None
        ai_template_version = self.config.template_version if self.config and hasattr(self.config, 'template_version') else None

        mutation = """
mutation CreateReport(
    $templateId: UUID,
    $templateVersion: Int,
    $type: String!,
    $title: String!,
    $status: String!,
    $scenarioId: UUID,
    $workspaceAnalysisId: UUID,
    $metadata: String
) {
    createReport(
        templateId: $templateId,
        templateVersion: $templateVersion,
        scenarioId: $scenarioId,
        workspaceAnalysisId: $workspaceAnalysisId,
        type: $type,
        title: $title,
        status: $status,
        metadata: $metadata
    )
}
"""

        variables = {
            "templateId": ai_template_id,
            "templateVersion": ai_template_version,
            "type": "analysis",
            "title": result.title,
            "status": "draft",
            "scenarioId": self.scenario_id if self.scenario_id else None,
            "workspaceAnalysisId": "<generated-workspace-analysis-id>" if not self.scenario_id else None,
            "metadata": None
        }

        return {
            "operation": f"#{self.mutation_count} CREATE_REPORT",
            "description": f"Create analysis report: {result.title}",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "UUID (report_id)"
        }

    def _create_scenario_report_mutation(
        self,
        result: ScenarioResult,
        parent_report_id: str
    ) -> Dict[str, Any]:
        """Generate createReport mutation for scenario."""
        self.mutation_count += 1

        ai_template_id = self.config.template_id if self.config and hasattr(self.config, 'template_id') else None
        ai_template_version = self.config.template_version if self.config and hasattr(self.config, 'template_version') else None

        mutation = """
mutation CreateReport(
    $templateId: UUID,
    $templateVersion: Int,
    $type: String!,
    $title: String!,
    $status: String!,
    $scenarioId: UUID!,
    $metadata: String
) {
    createReport(
        templateId: $templateId,
        templateVersion: $templateVersion,
        scenarioId: $scenarioId,
        type: $type,
        title: $title,
        status: $status,
        metadata: $metadata
    )
}
"""

        metadata = {
            "parent_analysis": result.parent_analysis,
            "parent_report_id": parent_report_id,
            "scenario_type": result.scenario_type
        }

        variables = {
            "templateId": ai_template_id,
            "templateVersion": ai_template_version,
            "type": "scenario",
            "title": result.title,
            "status": "draft",
            "scenarioId": self.scenario_id,
            "metadata": json.dumps(metadata)
        }

        return {
            "operation": f"#{self.mutation_count} CREATE_REPORT",
            "description": f"Create scenario report: {result.title} (parent: {parent_report_id})",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "UUID (report_id)"
        }

    def _create_source_mutation(
        self,
        report_id: str,
        source: SourceOutput,
        index: int
    ) -> Dict[str, Any]:
        """Generate createSource mutation."""
        self.mutation_count += 1

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

        variables = {
            "reportId": report_id,
            "sourceType": source.source_type.value,
            "uri": source.uri,
            "title": source.title,
            "description": source.description,
            "metadata": json.dumps(source.metadata) if source.metadata else None
        }

        return {
            "operation": f"#{self.mutation_count} CREATE_SOURCE",
            "description": f"Create source #{index}: [{source.source_type.value}] {source.title or source.source_id}",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "UUID (source_id)"
        }

    def _create_section_with_blocks(
        self,
        report_id: str,
        section: ReportSectionOutput,
        source_id_map: Dict[str, str],
        section_number: int
    ) -> List[Dict[str, Any]]:
        """Generate mutations for section and all its blocks."""
        mutations = []

        # Create section
        section_mutation = self._create_section_mutation(report_id, section, section_number)
        mutations.append(section_mutation)
        section_id = f"<generated-section-{section_number}>"

        # Create blocks
        for block_idx, block in enumerate(section.blocks):
            real_source_refs = [source_id_map.get(ref, ref) for ref in block.source_refs]
            block_mutations = self._create_block_mutation(
                section_id, block, real_source_refs, section_number, block_idx + 1
            )
            mutations.extend(block_mutations)

        return mutations

    def _create_section_mutation(
        self,
        report_id: str,
        section: ReportSectionOutput,
        section_number: int
    ) -> Dict[str, Any]:
        """Generate createReportSection mutation."""
        self.mutation_count += 1

        mutation = """
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

        variables = {
            "reportId": report_id,
            "templateSectionId": None,
            "sectionType": section.section_type.value,
            "header": section.header,
            "order": section.order
        }

        return {
            "operation": f"#{self.mutation_count} CREATE_SECTION",
            "description": f"Create section #{section_number}: {section.header} ({section.section_type.value})",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "UUID (section_id)"
        }

    def _convert_data_grid_to_markdown(self, content: DataGridContent) -> str:
        """Convert DataGridContent to markdown table format."""
        lines = []

        # Add title as H3 heading if present
        if content.title:
            lines.append(f"### {content.title}\n")

        # Build table header from column labels
        header_labels = [col.get("label", col.get("key", "")) for col in content.columns]
        lines.append("| " + " | ".join(header_labels) + " |")

        # Build separator row
        separators = ["-" * max(len(label), 3) for label in header_labels]
        lines.append("| " + " | ".join(separators) + " |")

        # Build data rows
        for row in content.rows:
            cells = []
            for col in content.columns:
                key = col.get("key", "")
                value = row.get(key, "")
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

        # Build table header from column labels
        header_labels = [col.get("label", col.get("key", "")) for col in content.columns]
        lines.append("| " + " | ".join(header_labels) + " |")

        # Build separator row
        separators = ["-" * max(len(label), 3) for label in header_labels]
        lines.append("| " + " | ".join(separators) + " |")

        # Build data rows
        for row in content.rows:
            cells = []
            for col in content.columns:
                key = col.get("key", "")
                value = row.get(key, "")
                # Convert to string and escape pipe characters
                cell_value = str(value) if value is not None else ""
                cell_value = cell_value.replace("|", "\\|")
                cells.append(cell_value)
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _create_block_mutation(
        self,
        section_id: str,
        block: ReportBlockOutput,
        source_refs: List[str],
        section_number: int,
        block_number: int
    ) -> List[Dict[str, Any]]:
        """Generate mutations for block creation and content."""
        mutations = []

        # Convert table block types to rich_text for DB storage
        # (DB doesn't support data_grid or comparison_table yet)
        actual_block_type = block.block_type
        if block.block_type in (BlockType.DATA_GRID, BlockType.COMPARISON_TABLE):
            actual_block_type = BlockType.RICH_TEXT

        # 1. Create block shell
        self.mutation_count += 1
        create_mutation = """
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

        create_variables = {
            "sectionId": section_id,
            "templateBlockId": None,
            "blockType": actual_block_type.value,  # Use RICH_TEXT for tables
            "order": block.order,
            "sourceRefs": source_refs,
            "layoutHints": json.dumps(block.layout_hints) if block.layout_hints else None
        }

        description = f"Create block S{section_number}.B{block_number}: {block.block_type.value}"
        if actual_block_type != block.block_type:
            description += f" (stored as {actual_block_type.value})"

        mutations.append({
            "operation": f"#{self.mutation_count} CREATE_BLOCK",
            "description": description,
            "mutation": create_mutation.strip(),
            "variables": create_variables,
            "returns": "UUID (block_id)"
        })

        block_id = f"<generated-block-S{section_number}B{block_number}>"

        # 2. Upsert content
        content_mutation = self._create_block_content_mutation(block_id, block, section_number, block_number)
        if content_mutation:
            mutations.append(content_mutation)

        return mutations

    def _create_block_content_mutation(
        self,
        block_id: str,
        block: ReportBlockOutput,
        section_number: int,
        block_number: int
    ) -> Optional[Dict[str, Any]]:
        """Generate content upsert mutation based on block type."""
        self.mutation_count += 1
        content = block.content

        if block.block_type == BlockType.RICH_TEXT:
            mutation = """
mutation UpsertRichText($blockId: UUID!, $content: String!) {
    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
}
"""
            variables = {
                "blockId": block_id,
                "content": content.markdown
            }
            preview = content.markdown[:100] + "..." if len(content.markdown) > 100 else content.markdown

        elif block.block_type == BlockType.SINGLE_METRIC:
            mutation = """
mutation UpsertSingleMetric(
    $blockId: UUID!,
    $label: String!,
    $value: String!,
    $unit: String,
    $trend: String
) {
    upsertReportBlockSingleMetric(
        reportBlockId: $blockId,
        label: $label,
        value: $value,
        unit: $unit,
        trend: $trend
    )
}
"""
            variables = {
                "blockId": block_id,
                "label": content.label,
                "value": content.value,
                "unit": content.unit,
                "trend": content.trend
            }
            preview = f"{content.label}: {content.value} {content.unit or ''}"

        elif block.block_type == BlockType.MULTI_METRIC:
            mutation = """
mutation UpsertMultiMetric($blockId: UUID!, $metrics: String!) {
    upsertReportBlockMultiMetric(reportBlockId: $blockId, metrics: $metrics)
}
"""
            variables = {
                "blockId": block_id,
                "metrics": json.dumps([m.model_dump() for m in content.metrics])
            }
            preview = f"{len(content.metrics)} metrics"

        elif block.block_type == BlockType.INSIGHT_CARD:
            mutation = """
mutation UpsertInsightCard(
    $blockId: UUID!,
    $title: String!,
    $body: String!,
    $badge: String,
    $severity: String
) {
    upsertReportBlockInsightCard(
        reportBlockId: $blockId,
        title: $title,
        body: $body,
        badge: $badge,
        severity: $severity
    )
}
"""
            variables = {
                "blockId": block_id,
                "title": content.title,
                "body": content.body,
                "badge": content.badge,
                "severity": content.severity
            }
            preview = f"{content.title}"

        elif block.block_type == BlockType.DATA_GRID:
            # Convert to markdown and persist as rich_text
            markdown = self._convert_data_grid_to_markdown(content)
            mutation = """
mutation UpsertRichText($blockId: UUID!, $content: String!) {
    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
}
"""
            variables = {
                "blockId": block_id,
                "content": markdown
            }
            preview = f"Data grid: {content.title or 'untitled'} ({len(content.rows)} rows, {len(content.columns)} cols)"

        elif block.block_type == BlockType.COMPARISON_TABLE:
            # Convert to markdown and persist as rich_text
            markdown = self._convert_comparison_table_to_markdown(content)
            mutation = """
mutation UpsertRichText($blockId: UUID!, $content: String!) {
    upsertReportBlockRichText(reportBlockId: $blockId, content: $content)
}
"""
            variables = {
                "blockId": block_id,
                "content": markdown
            }
            preview = f"Comparison table: {content.title or 'untitled'} ({len(content.rows)} rows, {len(content.columns)} cols)"

        else:
            # Unknown block type
            return None

        return {
            "operation": f"#{self.mutation_count} UPSERT_CONTENT",
            "description": f"Upsert content S{section_number}.B{block_number}: {preview}",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "Boolean"
        }

    def _update_report_status_mutation(self, report_id: str, status: str) -> Dict[str, Any]:
        """Generate updateReport mutation."""
        self.mutation_count += 1

        mutation = """
mutation UpdateReport($reportId: UUID!, $status: String!) {
    updateReport(reportId: $reportId, status: $status)
}
"""

        variables = {
            "reportId": report_id,
            "status": status
        }

        return {
            "operation": f"#{self.mutation_count} UPDATE_STATUS",
            "description": f"Update report status to: {status}",
            "mutation": mutation.strip(),
            "variables": variables,
            "returns": "Boolean"
        }

    def print_mutations(self, mutations: List[Dict[str, Any]], verbose: bool = False):
        """Pretty-print mutations to console."""
        print("\n" + "=" * 80)
        print(f"GRAPHQL MUTATIONS PREVIEW ({len(mutations)} operations)")
        print("=" * 80)

        for mutation in mutations:
            print(f"\n{mutation['operation']}")
            print(f"Description: {mutation['description']}")
            print(f"Returns: {mutation['returns']}")

            if verbose:
                print("\nMutation:")
                print(self._indent(mutation['mutation'], 2))
                print("\nVariables:")
                print(self._indent(json.dumps(mutation['variables'], indent=2), 2))

            print("-" * 80)

        print(f"\nTotal operations: {len(mutations)}")
        print("=" * 80)

    @staticmethod
    def _indent(text: str, spaces: int) -> str:
        """Indent each line of text."""
        indent = " " * spaces
        return "\n".join(indent + line for line in text.split("\n"))
