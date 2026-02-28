using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class MakeWorkspaceItemPkSurrogate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropPrimaryKey(
                name: "pk_workspace_items",
                schema: "app",
                table: "workspace_items");

            migrationBuilder.AlterColumn<string>(
                name: "graph_edge_id",
                schema: "app",
                table: "workspace_items",
                type: "text",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "text");

            // Add new surrogate key column as nullable first
            migrationBuilder.AddColumn<Guid>(
                name: "workspace_item_id",
                schema: "app",
                table: "workspace_items",
                type: "uuid",
                nullable: true);

            // Backfill unique values without relying on extensions (Azure PG safe)
            migrationBuilder.Sql(@"UPDATE app.workspace_items SET workspace_item_id = (
                (
                    substr(md5(random()::text || clock_timestamp()::text), 1, 8) || '-' ||
                    substr(md5(random()::text || clock_timestamp()::text), 9, 4) || '-' ||
                    substr(md5(random()::text || clock_timestamp()::text), 13, 4) || '-' ||
                    substr(md5(random()::text || clock_timestamp()::text), 17, 4) || '-' ||
                    substr(md5(random()::text || clock_timestamp()::text), 21, 12)
                )::uuid
            ) WHERE workspace_item_id IS NULL;");

            // Make the new column not null
            migrationBuilder.AlterColumn<Guid>(
                name: "workspace_item_id",
                schema: "app",
                table: "workspace_items",
                type: "uuid",
                nullable: false,
                oldClrType: typeof(Guid),
                oldType: "uuid",
                oldNullable: true);

            // Add new primary key on surrogate column
            migrationBuilder.AddPrimaryKey(
                name: "pk_workspace_items",
                schema: "app",
                table: "workspace_items",
                column: "workspace_item_id");

            // Preserve idempotency semantics with a unique index
            migrationBuilder.CreateIndex(
                name: "ix_workspace_items_workspace_id_graph_node_id_graph_edge_id",
                schema: "app",
                table: "workspace_items",
                columns: new[] { "workspace_id", "graph_node_id", "graph_edge_id" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropPrimaryKey(
                name: "pk_workspace_items",
                schema: "app",
                table: "workspace_items");

            migrationBuilder.DropIndex(
                name: "ix_workspace_items_workspace_id_graph_node_id_graph_edge_id",
                schema: "app",
                table: "workspace_items");

            migrationBuilder.DropColumn(
                name: "workspace_item_id",
                schema: "app",
                table: "workspace_items");

            migrationBuilder.AlterColumn<string>(
                name: "graph_edge_id",
                schema: "app",
                table: "workspace_items",
                type: "text",
                nullable: false,
                defaultValue: "",
                oldClrType: typeof(string),
                oldType: "text",
                oldNullable: true);

            migrationBuilder.AddPrimaryKey(
                name: "pk_workspace_items",
                schema: "app",
                table: "workspace_items",
                columns: new[] { "workspace_id", "graph_node_id", "graph_edge_id" });
        }
    }
}
