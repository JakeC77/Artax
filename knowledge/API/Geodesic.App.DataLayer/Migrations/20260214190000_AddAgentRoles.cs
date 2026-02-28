using System;
using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20260214190000_AddAgentRoles")]
    public partial class AddAgentRoles : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "agent_roles",
                schema: "app",
                columns: table => new
                {
                    agent_role_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    read_ontology_id = table.Column<Guid>(type: "uuid", nullable: true),
                    write_ontology_id = table.Column<Guid>(type: "uuid", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    last_edit = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_agent_roles", x => x.agent_role_id);
                    table.ForeignKey(
                        name: "fk_agent_roles_ontologies_read_ontology_id",
                        column: x => x.read_ontology_id,
                        principalSchema: "app",
                        principalTable: "ontologies",
                        principalColumn: "ontology_id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "fk_agent_roles_ontologies_write_ontology_id",
                        column: x => x.write_ontology_id,
                        principalSchema: "app",
                        principalTable: "ontologies",
                        principalColumn: "ontology_id",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateTable(
                name: "agent_role_access_keys",
                schema: "app",
                columns: table => new
                {
                    access_key_id = table.Column<Guid>(type: "uuid", nullable: false),
                    agent_role_id = table.Column<Guid>(type: "uuid", nullable: false),
                    key_hash = table.Column<string>(type: "text", nullable: false),
                    key_prefix = table.Column<string>(type: "text", nullable: false),
                    name = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    expires_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_agent_role_access_keys", x => x.access_key_id);
                    table.ForeignKey(
                        name: "fk_agent_role_access_keys_agent_roles_agent_role_id",
                        column: x => x.agent_role_id,
                        principalSchema: "app",
                        principalTable: "agent_roles",
                        principalColumn: "agent_role_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "agent_role_intents",
                schema: "app",
                columns: table => new
                {
                    agent_role_id = table.Column<Guid>(type: "uuid", nullable: false),
                    intent_id = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_agent_role_intents", x => new { x.agent_role_id, x.intent_id });
                    table.ForeignKey(
                        name: "fk_agent_role_intents_agent_roles_agent_role_id",
                        column: x => x.agent_role_id,
                        principalSchema: "app",
                        principalTable: "agent_roles",
                        principalColumn: "agent_role_id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "fk_agent_role_intents_intents_intent_id",
                        column: x => x.intent_id,
                        principalSchema: "app",
                        principalTable: "intents",
                        principalColumn: "intent_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_agent_roles_read_ontology_id",
                schema: "app",
                table: "agent_roles",
                column: "read_ontology_id");

            migrationBuilder.CreateIndex(
                name: "ix_agent_roles_tenant_id",
                schema: "app",
                table: "agent_roles",
                column: "tenant_id");

            migrationBuilder.CreateIndex(
                name: "ix_agent_roles_tenant_id_name",
                schema: "app",
                table: "agent_roles",
                columns: new[] { "tenant_id", "name" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_agent_roles_write_ontology_id",
                schema: "app",
                table: "agent_roles",
                column: "write_ontology_id");

            migrationBuilder.CreateIndex(
                name: "ix_agent_role_access_keys_agent_role_id",
                schema: "app",
                table: "agent_role_access_keys",
                column: "agent_role_id");

            migrationBuilder.CreateIndex(
                name: "ix_agent_role_intents_intent_id",
                schema: "app",
                table: "agent_role_intents",
                column: "intent_id");
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "agent_role_access_keys",
                schema: "app");

            migrationBuilder.DropTable(
                name: "agent_role_intents",
                schema: "app");

            migrationBuilder.DropTable(
                name: "agent_roles",
                schema: "app");
        }
    }
}
