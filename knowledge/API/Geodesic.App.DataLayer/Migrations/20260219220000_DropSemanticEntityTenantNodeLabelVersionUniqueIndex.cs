using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20260219220000_DropSemanticEntityTenantNodeLabelVersionUniqueIndex")]
    public partial class DropSemanticEntityTenantNodeLabelVersionUniqueIndex : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_semantic_entities_tenant_id_node_label_version",
                schema: "app",
                table: "semantic_entities");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateIndex(
                name: "ix_semantic_entities_tenant_id_node_label_version",
                schema: "app",
                table: "semantic_entities",
                columns: new[] { "tenant_id", "node_label", "version" },
                unique: true);
        }
    }
}
