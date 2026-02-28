using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddAITeamsAndUpdateMembers : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ai_team_members",
                schema: "app");

            migrationBuilder.CreateTable(
                name: "ai_teams",
                schema: "app",
                columns: table => new
                {
                    ai_team_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_ai_teams", x => x.ai_team_id);
                    table.ForeignKey(
                        name: "fk_ai_teams_workspaces_workspace_id",
                        column: x => x.workspace_id,
                        principalSchema: "app",
                        principalTable: "workspaces",
                        principalColumn: "workspace_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ai_team_members",
                schema: "app",
                columns: table => new
                {
                    ai_team_member_id = table.Column<Guid>(type: "uuid", nullable: false),
                    ai_team_id = table.Column<Guid>(type: "uuid", nullable: false),
                    agent_id = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    role = table.Column<string>(type: "text", nullable: false),
                    system_prompt = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    model = table.Column<string>(type: "text", nullable: true),
                    temperature = table.Column<decimal>(type: "numeric", nullable: true),
                    max_tokens = table.Column<int>(type: "integer", nullable: true),
                    tools = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    expertise = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    communication_style = table.Column<string>(type: "text", nullable: true),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_ai_team_members", x => x.ai_team_member_id);
                    table.ForeignKey(
                        name: "fk_ai_team_members_ai_teams_ai_team_id",
                        column: x => x.ai_team_id,
                        principalSchema: "app",
                        principalTable: "ai_teams",
                        principalColumn: "ai_team_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_ai_teams_workspace_id",
                schema: "app",
                table: "ai_teams",
                column: "workspace_id",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_ai_team_members_ai_team_id_agent_id",
                schema: "app",
                table: "ai_team_members",
                columns: new[] { "ai_team_id", "agent_id" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ai_team_members",
                schema: "app");

            migrationBuilder.DropTable(
                name: "ai_teams",
                schema: "app");

            migrationBuilder.CreateTable(
                name: "ai_team_members",
                schema: "app",
                columns: table => new
                {
                    ai_team_member_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    name = table.Column<string>(type: "text", nullable: false),
                    prompt = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_ai_team_members", x => x.ai_team_member_id);
                });
        }
    }
}
