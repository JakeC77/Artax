using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddReportSystem : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "report_templates",
                schema: "app",
                columns: table => new
                {
                    template_id = table.Column<Guid>(type: "uuid", nullable: false),
                    version = table.Column<int>(type: "integer", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_templates", x => new { x.template_id, x.version });
                });

            migrationBuilder.CreateTable(
                name: "report_template_sections",
                schema: "app",
                columns: table => new
                {
                    template_section_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_version = table.Column<int>(type: "integer", nullable: false),
                    section_type = table.Column<string>(type: "text", nullable: false),
                    header = table.Column<string>(type: "text", nullable: false),
                    order = table.Column<int>(type: "integer", nullable: false),
                    semantic_definition = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_template_sections", x => x.template_section_id);
                    table.ForeignKey(
                        name: "fk_report_template_sections_report_templates_template_id_templ",
                        columns: x => new { x.template_id, x.template_version },
                        principalSchema: "app",
                        principalTable: "report_templates",
                        principalColumns: new[] { "template_id", "version" },
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "reports",
                schema: "app",
                columns: table => new
                {
                    report_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_version = table.Column<int>(type: "integer", nullable: false),
                    workspace_analysis_id = table.Column<Guid>(type: "uuid", nullable: true),
                    scenario_id = table.Column<Guid>(type: "uuid", nullable: true),
                    type = table.Column<string>(type: "text", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    status = table.Column<string>(type: "text", nullable: false),
                    metadata = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_reports", x => x.report_id);
                    table.CheckConstraint("ck_report_parent", "(workspace_analysis_id IS NOT NULL AND scenario_id IS NULL) OR (workspace_analysis_id IS NULL AND scenario_id IS NOT NULL)");
                    table.ForeignKey(
                        name: "fk_reports_report_templates_template_id_template_version",
                        columns: x => new { x.template_id, x.template_version },
                        principalSchema: "app",
                        principalTable: "report_templates",
                        principalColumns: new[] { "template_id", "version" },
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "fk_reports_scenarios_scenario_id",
                        column: x => x.scenario_id,
                        principalSchema: "app",
                        principalTable: "scenarios",
                        principalColumn: "scenario_id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_reports_workspace_analyses_workspace_analysis_id",
                        column: x => x.workspace_analysis_id,
                        principalSchema: "app",
                        principalTable: "workspace_analyses",
                        principalColumn: "workspace_analysis_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_template_blocks",
                schema: "app",
                columns: table => new
                {
                    template_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_section_id = table.Column<Guid>(type: "uuid", nullable: false),
                    block_type = table.Column<string>(type: "text", nullable: false),
                    order = table.Column<int>(type: "integer", nullable: false),
                    layout_hints = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    semantic_definition = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_template_blocks", x => x.template_block_id);
                    table.ForeignKey(
                        name: "fk_report_template_blocks_report_template_sections_template_se",
                        column: x => x.template_section_id,
                        principalSchema: "app",
                        principalTable: "report_template_sections",
                        principalColumn: "template_section_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_sections",
                schema: "app",
                columns: table => new
                {
                    report_section_id = table.Column<Guid>(type: "uuid", nullable: false),
                    report_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_section_id = table.Column<Guid>(type: "uuid", nullable: false),
                    section_type = table.Column<string>(type: "text", nullable: false),
                    header = table.Column<string>(type: "text", nullable: false),
                    order = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_sections", x => x.report_section_id);
                    table.ForeignKey(
                        name: "fk_report_sections_report_template_sections_template_section_id",
                        column: x => x.template_section_id,
                        principalSchema: "app",
                        principalTable: "report_template_sections",
                        principalColumn: "template_section_id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "fk_report_sections_reports_report_id",
                        column: x => x.report_id,
                        principalSchema: "app",
                        principalTable: "reports",
                        principalColumn: "report_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "sources",
                schema: "app",
                columns: table => new
                {
                    source_id = table.Column<Guid>(type: "uuid", nullable: false),
                    report_id = table.Column<Guid>(type: "uuid", nullable: false),
                    source_type = table.Column<string>(type: "text", nullable: false),
                    uri = table.Column<string>(type: "text", nullable: true),
                    title = table.Column<string>(type: "text", nullable: true),
                    description = table.Column<string>(type: "text", nullable: true),
                    metadata = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_sources", x => x.source_id);
                    table.ForeignKey(
                        name: "fk_sources_reports_report_id",
                        column: x => x.report_id,
                        principalSchema: "app",
                        principalTable: "reports",
                        principalColumn: "report_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_blocks",
                schema: "app",
                columns: table => new
                {
                    report_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    report_section_id = table.Column<Guid>(type: "uuid", nullable: false),
                    template_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    block_type = table.Column<string>(type: "text", nullable: false),
                    source_refs = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    provenance = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    layout_hints = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    order = table.Column<int>(type: "integer", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_blocks", x => x.report_block_id);
                    table.ForeignKey(
                        name: "fk_report_blocks_report_sections_report_section_id",
                        column: x => x.report_section_id,
                        principalSchema: "app",
                        principalTable: "report_sections",
                        principalColumn: "report_section_id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_report_blocks_report_template_blocks_template_block_id",
                        column: x => x.template_block_id,
                        principalSchema: "app",
                        principalTable: "report_template_blocks",
                        principalColumn: "template_block_id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "report_block_insight_cards",
                schema: "app",
                columns: table => new
                {
                    report_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    body = table.Column<string>(type: "text", nullable: false),
                    badge = table.Column<string>(type: "text", nullable: true),
                    severity = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_block_insight_cards", x => x.report_block_id);
                    table.ForeignKey(
                        name: "fk_report_block_insight_cards_report_blocks_report_block_id",
                        column: x => x.report_block_id,
                        principalSchema: "app",
                        principalTable: "report_blocks",
                        principalColumn: "report_block_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_block_multi_metrics",
                schema: "app",
                columns: table => new
                {
                    report_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    metrics = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'[]'::jsonb")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_block_multi_metrics", x => x.report_block_id);
                    table.ForeignKey(
                        name: "fk_report_block_multi_metrics_report_blocks_report_block_id",
                        column: x => x.report_block_id,
                        principalSchema: "app",
                        principalTable: "report_blocks",
                        principalColumn: "report_block_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_block_rich_texts",
                schema: "app",
                columns: table => new
                {
                    report_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    content = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_block_rich_texts", x => x.report_block_id);
                    table.ForeignKey(
                        name: "fk_report_block_rich_texts_report_blocks_report_block_id",
                        column: x => x.report_block_id,
                        principalSchema: "app",
                        principalTable: "report_blocks",
                        principalColumn: "report_block_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "report_block_single_metrics",
                schema: "app",
                columns: table => new
                {
                    report_block_id = table.Column<Guid>(type: "uuid", nullable: false),
                    label = table.Column<string>(type: "text", nullable: false),
                    value = table.Column<string>(type: "text", nullable: false),
                    unit = table.Column<string>(type: "text", nullable: true),
                    trend = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_report_block_single_metrics", x => x.report_block_id);
                    table.ForeignKey(
                        name: "fk_report_block_single_metrics_report_blocks_report_block_id",
                        column: x => x.report_block_id,
                        principalSchema: "app",
                        principalTable: "report_blocks",
                        principalColumn: "report_block_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_report_blocks_report_section_id",
                schema: "app",
                table: "report_blocks",
                column: "report_section_id");

            migrationBuilder.CreateIndex(
                name: "ix_report_blocks_template_block_id",
                schema: "app",
                table: "report_blocks",
                column: "template_block_id");

            migrationBuilder.CreateIndex(
                name: "ix_report_sections_report_id",
                schema: "app",
                table: "report_sections",
                column: "report_id");

            migrationBuilder.CreateIndex(
                name: "ix_report_sections_template_section_id",
                schema: "app",
                table: "report_sections",
                column: "template_section_id");

            migrationBuilder.CreateIndex(
                name: "ix_report_template_blocks_template_section_id",
                schema: "app",
                table: "report_template_blocks",
                column: "template_section_id");

            migrationBuilder.CreateIndex(
                name: "ix_report_template_sections_template_id_template_version",
                schema: "app",
                table: "report_template_sections",
                columns: new[] { "template_id", "template_version" });

            migrationBuilder.CreateIndex(
                name: "ix_report_templates_template_id_version",
                schema: "app",
                table: "report_templates",
                columns: new[] { "template_id", "version" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_reports_scenario_id",
                schema: "app",
                table: "reports",
                column: "scenario_id");

            migrationBuilder.CreateIndex(
                name: "ix_reports_template_id",
                schema: "app",
                table: "reports",
                column: "template_id");

            migrationBuilder.CreateIndex(
                name: "ix_reports_template_id_template_version",
                schema: "app",
                table: "reports",
                columns: new[] { "template_id", "template_version" });

            migrationBuilder.CreateIndex(
                name: "ix_reports_workspace_analysis_id",
                schema: "app",
                table: "reports",
                column: "workspace_analysis_id");

            migrationBuilder.CreateIndex(
                name: "ix_sources_report_id",
                schema: "app",
                table: "sources",
                column: "report_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "report_block_insight_cards",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_block_multi_metrics",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_block_rich_texts",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_block_single_metrics",
                schema: "app");

            migrationBuilder.DropTable(
                name: "sources",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_blocks",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_sections",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_template_blocks",
                schema: "app");

            migrationBuilder.DropTable(
                name: "reports",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_template_sections",
                schema: "app");

            migrationBuilder.DropTable(
                name: "report_templates",
                schema: "app");
        }
    }
}
