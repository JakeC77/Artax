using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddWorkspaceIdToScenarioRuns : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Add workspace_id column as nullable initially
            migrationBuilder.AddColumn<Guid>(
                name: "workspace_id",
                schema: "app",
                table: "scenario_runs",
                type: "uuid",
                nullable: true);

            // Backfill workspace_id from scenarios table
            migrationBuilder.Sql(@"
                UPDATE app.scenario_runs sr
                SET workspace_id = s.workspace_id
                FROM app.scenarios s
                WHERE sr.scenario_id = s.scenario_id
            ");

            // Set workspace_id to NOT NULL after backfill
            migrationBuilder.AlterColumn<Guid>(
                name: "workspace_id",
                schema: "app",
                table: "scenario_runs",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            // Make scenario_id nullable
            migrationBuilder.AlterColumn<Guid>(
                name: "scenario_id",
                schema: "app",
                table: "scenario_runs",
                type: "uuid",
                nullable: true,
                oldClrType: typeof(Guid),
                oldType: "uuid");

            // Create index on workspace_id for query performance
            migrationBuilder.CreateIndex(
                name: "ix_scenario_runs_workspace_id",
                schema: "app",
                table: "scenario_runs",
                column: "workspace_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_scenario_runs_workspace_id",
                schema: "app",
                table: "scenario_runs");

            migrationBuilder.DropColumn(
                name: "workspace_id",
                schema: "app",
                table: "scenario_runs");

            migrationBuilder.AlterColumn<Guid>(
                name: "scenario_id",
                schema: "app",
                table: "scenario_runs",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"),
                oldClrType: typeof(Guid),
                oldType: "uuid",
                oldNullable: true);
        }
    }
}
