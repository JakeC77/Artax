using System;
using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    [DbContext(typeof(AppDbContext))]
    [Migration("20260129140000_AddDataLoadingAttachments")]
    public partial class AddDataLoadingAttachments : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "data_loading_attachments",
                schema: "app",
                columns: table => new
                {
                    attachment_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    ontology_id = table.Column<Guid>(type: "uuid", nullable: false),
                    file_name = table.Column<string>(type: "text", nullable: false),
                    blob_path = table.Column<string>(type: "text", nullable: false),
                    uri = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    created_by = table.Column<Guid>(type: "uuid", nullable: true),
                    run_id = table.Column<Guid>(type: "uuid", nullable: true),
                    status = table.Column<string>(type: "text", nullable: false, defaultValue: "uploaded")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_data_loading_attachments", x => x.attachment_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_data_loading_attachments_tenant_id",
                schema: "app",
                table: "data_loading_attachments",
                column: "tenant_id");

            migrationBuilder.CreateIndex(
                name: "ix_data_loading_attachments_ontology_id",
                schema: "app",
                table: "data_loading_attachments",
                column: "ontology_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "data_loading_attachments",
                schema: "app");
        }
    }
}
