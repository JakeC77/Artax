using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddIntents : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "intents",
                schema: "app",
                columns: table => new
                {
                    intent_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    op_id = table.Column<string>(type: "text", nullable: false),
                    intent_name = table.Column<string>(type: "text", nullable: false),
                    route = table.Column<string>(type: "text", nullable: true),
                    description = table.Column<string>(type: "text", nullable: true),
                    data_source = table.Column<string>(type: "text", nullable: true),
                    input_schema = table.Column<string>(type: "jsonb", nullable: true),
                    output_schema = table.Column<string>(type: "jsonb", nullable: true),
                    grounding = table.Column<string>(type: "jsonb", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    last_edit = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_intents", x => x.intent_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_intents_tenant_id",
                schema: "app",
                table: "intents",
                column: "tenant_id");

            migrationBuilder.CreateIndex(
                name: "ix_intents_tenant_id_op_id",
                schema: "app",
                table: "intents",
                columns: new[] { "tenant_id", "op_id" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "intents",
                schema: "app");
        }
    }
}
