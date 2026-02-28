using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddWorkspaceSetupFlow : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "setup_completed_at",
                schema: "app",
                table: "workspaces",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "setup_data_scope",
                schema: "app",
                table: "workspaces",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "setup_execution_results",
                schema: "app",
                table: "workspaces",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "setup_intent_package",
                schema: "app",
                table: "workspaces",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "setup_stage",
                schema: "app",
                table: "workspaces",
                type: "text",
                nullable: false,
                defaultValue: "intent_discovery");

            migrationBuilder.AddColumn<DateTimeOffset>(
                name: "setup_started_at",
                schema: "app",
                table: "workspaces",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "setup_team_config",
                schema: "app",
                table: "workspaces",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "state",
                schema: "app",
                table: "workspaces",
                type: "text",
                nullable: false,
                defaultValue: "draft");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "setup_completed_at",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_data_scope",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_execution_results",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_intent_package",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_stage",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_started_at",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "setup_team_config",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "state",
                schema: "app",
                table: "workspaces");
        }
    }
}
