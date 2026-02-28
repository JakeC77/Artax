using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddSemanticModels : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "semantic_entities",
                schema: "app",
                columns: table => new
                {
                    semantic_entity_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    node_label = table.Column<string>(type: "text", nullable: false),
                    version = table.Column<int>(type: "integer", nullable: false, defaultValue: 1),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_semantic_entities", x => x.semantic_entity_id);
                });

            migrationBuilder.CreateTable(
                name: "semantic_fields",
                schema: "app",
                columns: table => new
                {
                    semantic_field_id = table.Column<Guid>(type: "uuid", nullable: false),
                    semantic_entity_id = table.Column<Guid>(type: "uuid", nullable: false),
                    version = table.Column<int>(type: "integer", nullable: false, defaultValue: 1),
                    name = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_semantic_fields", x => x.semantic_field_id);
                    table.ForeignKey(
                        name: "fk_semantic_fields_semantic_entities_semantic_entity_id",
                        column: x => x.semantic_entity_id,
                        principalSchema: "app",
                        principalTable: "semantic_entities",
                        principalColumn: "semantic_entity_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "ix_semantic_entities_tenant_id_node_label_version",
                schema: "app",
                table: "semantic_entities",
                columns: new[] { "tenant_id", "node_label", "version" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_semantic_fields_semantic_entity_id",
                schema: "app",
                table: "semantic_fields",
                column: "semantic_entity_id");

            migrationBuilder.CreateIndex(
                name: "ix_semantic_fields_semantic_entity_id_name_version",
                schema: "app",
                table: "semantic_fields",
                columns: new[] { "semantic_entity_id", "name", "version" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "semantic_fields",
                schema: "app");

            migrationBuilder.DropTable(
                name: "semantic_entities",
                schema: "app");
        }
    }
}
