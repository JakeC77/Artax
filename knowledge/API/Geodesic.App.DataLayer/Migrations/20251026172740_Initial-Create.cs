using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.EnsureSchema(
                name: "app");

            
            migrationBuilder.CreateTable(
                name: "insights",
                schema: "app",
                columns: table => new
                {
                    insight_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: true),
                    severity = table.Column<string>(type: "text", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    body = table.Column<string>(type: "text", nullable: false),
                    related_graph_ids = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    evidence_refs = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'[]'::jsonb"),
                    generated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_insights", x => x.insight_id);
                });

            migrationBuilder.CreateTable(
                name: "overlay_changesets",
                schema: "app",
                columns: table => new
                {
                    changeset_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    created_by = table.Column<Guid>(type: "uuid", nullable: false),
                    status = table.Column<string>(type: "text", nullable: false, defaultValue: "draft"),
                    comment = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_overlay_changesets", x => x.changeset_id);
                });

            migrationBuilder.CreateTable(
                name: "overlay_edge_patch",
                schema: "app",
                columns: table => new
                {
                    changeset_id = table.Column<Guid>(type: "uuid", nullable: false),
                    graph_edge_id = table.Column<string>(type: "text", nullable: false),
                    op = table.Column<string>(type: "text", nullable: false, defaultValue: "upsert"),
                    patch = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_overlay_edge_patch", x => new { x.changeset_id, x.graph_edge_id });
                });

            migrationBuilder.CreateTable(
                name: "overlay_node_patch",
                schema: "app",
                columns: table => new
                {
                    changeset_id = table.Column<Guid>(type: "uuid", nullable: false),
                    graph_node_id = table.Column<string>(type: "text", nullable: false),
                    op = table.Column<string>(type: "text", nullable: false, defaultValue: "upsert"),
                    patch = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_overlay_node_patch", x => new { x.changeset_id, x.graph_node_id });
                });

            migrationBuilder.CreateTable(
                name: "roles",
                schema: "app",
                columns: table => new
                {
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    role_name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_roles", x => new { x.tenant_id, x.role_name });
                });

            migrationBuilder.CreateTable(
                name: "scenario_runs",
                schema: "app",
                columns: table => new
                {
                    run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    scenario_id = table.Column<Guid>(type: "uuid", nullable: false),
                    engine = table.Column<string>(type: "text", nullable: false),
                    inputs = table.Column<string>(type: "text", nullable: false),
                    outputs = table.Column<string>(type: "text", nullable: true),
                    status = table.Column<string>(type: "text", nullable: false, defaultValue: "queued"),
                    error_message = table.Column<string>(type: "text", nullable: true),
                    artifacts_uri = table.Column<string>(type: "text", nullable: true),
                    started_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    finished_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scenario_runs", x => x.run_id);
                });

            migrationBuilder.CreateTable(
                name: "scenarios",
                schema: "app",
                columns: table => new
                {
                    scenario_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    related_changeset_id = table.Column<Guid>(type: "uuid", nullable: true),
                    created_by = table.Column<Guid>(type: "uuid", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scenarios", x => x.scenario_id);
                });

            migrationBuilder.CreateTable(
                name: "tenants",
                schema: "app",
                columns: table => new
                {
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    region = table.Column<string>(type: "text", nullable: false, defaultValue: "us"),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_tenants", x => x.tenant_id);
                });

            migrationBuilder.CreateTable(
                name: "user_roles",
                schema: "app",
                columns: table => new
                {
                    user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    role_name = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_user_roles", x => new { x.user_id, x.role_name });
                });

            migrationBuilder.CreateTable(
                name: "users",
                schema: "app",
                columns: table => new
                {
                    user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    subject = table.Column<string>(type: "text", nullable: false),
                    email = table.Column<string>(type: "text", nullable: false),
                    display_name = table.Column<string>(type: "text", nullable: false),
                    is_admin = table.Column<bool>(type: "boolean", nullable: false),
                    preferences = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_users", x => x.user_id);
                });

            migrationBuilder.CreateTable(
                name: "workspace_items",
                schema: "app",
                columns: table => new
                {
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    graph_node_id = table.Column<string>(type: "text", nullable: false),
                    graph_edge_id = table.Column<string>(type: "text", nullable: false),
                    labels = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    pinned_by = table.Column<Guid>(type: "uuid", nullable: false),
                    pinned_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_workspace_items", x => new { x.workspace_id, x.graph_node_id, x.graph_edge_id });
                });

            migrationBuilder.CreateTable(
                name: "workspace_members",
                schema: "app",
                columns: table => new
                {
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    role = table.Column<string>(type: "text", nullable: false, defaultValue: "viewer"),
                    added_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_workspace_members", x => new { x.workspace_id, x.user_id });
                });

            migrationBuilder.CreateTable(
                name: "workspaces",
                schema: "app",
                columns: table => new
                {
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    owner_user_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    visibility = table.Column<string>(type: "text", nullable: false, defaultValue: "private"),
                    base_snapshot_ts = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_workspaces", x => x.workspace_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_scenarios_workspace_id_name",
                schema: "app",
                table: "scenarios",
                columns: new[] { "workspace_id", "name" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_users_tenant_id_email",
                schema: "app",
                table: "users",
                columns: new[] { "tenant_id", "email" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_users_tenant_id_subject",
                schema: "app",
                table: "users",
                columns: new[] { "tenant_id", "subject" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_tenant_id",
                schema: "app",
                table: "workspaces",
                column: "tenant_id");

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_tenant_id_name",
                schema: "app",
                table: "workspaces",
                columns: new[] { "tenant_id", "name" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "insights",
                schema: "app");

            migrationBuilder.DropTable(
                name: "overlay_changesets",
                schema: "app");

            migrationBuilder.DropTable(
                name: "overlay_edge_patch",
                schema: "app");

            migrationBuilder.DropTable(
                name: "overlay_node_patch",
                schema: "app");

            migrationBuilder.DropTable(
                name: "roles",
                schema: "app");

            migrationBuilder.DropTable(
                name: "scenario_runs",
                schema: "app");

            migrationBuilder.DropTable(
                name: "scenarios",
                schema: "app");

            migrationBuilder.DropTable(
                name: "tenants",
                schema: "app");

            migrationBuilder.DropTable(
                name: "user_roles",
                schema: "app");

            migrationBuilder.DropTable(
                name: "users",
                schema: "app");

            migrationBuilder.DropTable(
                name: "workspace_items",
                schema: "app");

            migrationBuilder.DropTable(
                name: "workspace_members",
                schema: "app");

            migrationBuilder.DropTable(
                name: "workspaces",
                schema: "app");
        }
    }
}
