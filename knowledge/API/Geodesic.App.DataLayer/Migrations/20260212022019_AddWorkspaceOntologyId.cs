using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddWorkspaceOntologyId : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "ontology_id",
                schema: "app",
                table: "workspaces",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_ontology_id",
                schema: "app",
                table: "workspaces",
                column: "ontology_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_workspaces_ontology_id",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "ontology_id",
                schema: "app",
                table: "workspaces");
        }
    }
}
