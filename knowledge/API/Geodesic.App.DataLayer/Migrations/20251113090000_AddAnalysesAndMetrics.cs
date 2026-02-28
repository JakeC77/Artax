using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    [DbContext(typeof(AppDbContext))]
    [Migration("20251113090000_AddAnalysesAndMetrics")]
    public partial class AddAnalysesAndMetrics : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Add new columns to scenarios
            migrationBuilder.AddColumn<string>(
                name: "header_text",
                schema: "app",
                table: "scenarios",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "main_text",
                schema: "app",
                table: "scenarios",
                type: "text",
                nullable: true);

            // Create workspace_analyses
            migrationBuilder.CreateTable(
                name: "workspace_analyses",
                schema: "app",
                columns: table => new
                {
                    workspace_analysis_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    title_text = table.Column<string>(type: "text", nullable: false),
                    body_text = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    version = table.Column<int>(type: "integer", nullable: false, defaultValue: 1)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_workspace_analyses", x => x.workspace_analysis_id);
                });

            // Create workspace_analysis_metrics
            migrationBuilder.CreateTable(
                name: "workspace_analysis_metrics",
                schema: "app",
                columns: table => new
                {
                    workspace_analysis_metric_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_analysis_id = table.Column<Guid>(type: "uuid", nullable: false),
                    main_text = table.Column<string>(type: "text", nullable: true),
                    secondary_text = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_workspace_analysis_metrics", x => x.workspace_analysis_metric_id);
                });

            // Create scenario_metrics
            migrationBuilder.CreateTable(
                name: "scenario_metrics",
                schema: "app",
                columns: table => new
                {
                    scenario_metric_id = table.Column<Guid>(type: "uuid", nullable: false),
                    scenario_id = table.Column<Guid>(type: "uuid", nullable: false),
                    main_text = table.Column<string>(type: "text", nullable: true),
                    secondary_text = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    version = table.Column<int>(type: "integer", nullable: false, defaultValue: 1)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scenario_metrics", x => x.scenario_metric_id);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "workspace_analysis_metrics",
                schema: "app");

            migrationBuilder.DropTable(
                name: "scenario_metrics",
                schema: "app");

            migrationBuilder.DropTable(
                name: "workspace_analyses",
                schema: "app");

            migrationBuilder.DropColumn(
                name: "header_text",
                schema: "app",
                table: "scenarios");

            migrationBuilder.DropColumn(
                name: "main_text",
                schema: "app",
                table: "scenarios");
        }
    }
}

