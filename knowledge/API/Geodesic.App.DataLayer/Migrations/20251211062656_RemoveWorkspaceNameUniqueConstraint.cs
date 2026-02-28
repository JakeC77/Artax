using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class RemoveWorkspaceNameUniqueConstraint : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_workspaces_tenant_id_name",
                schema: "app",
                table: "workspaces");

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_tenant_id_name",
                schema: "app",
                table: "workspaces",
                columns: new[] { "tenant_id", "name" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_workspaces_tenant_id_name",
                schema: "app",
                table: "workspaces");

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_tenant_id_name",
                schema: "app",
                table: "workspaces",
                columns: new[] { "tenant_id", "name" },
                unique: true);
        }
    }
}
