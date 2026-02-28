using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddCompaniesAndCompanyLinks : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "company_id",
                schema: "app",
                table: "workspaces",
                type: "uuid",
                nullable: true);

            migrationBuilder.AddColumn<Guid>(
                name: "company_id",
                schema: "app",
                table: "ontologies",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "companies",
                schema: "app",
                columns: table => new
                {
                    company_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    markdown_content = table.Column<string>(type: "text", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_companies", x => x.company_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_workspaces_company_id",
                schema: "app",
                table: "workspaces",
                column: "company_id");

            migrationBuilder.CreateIndex(
                name: "ix_ontologies_company_id",
                schema: "app",
                table: "ontologies",
                column: "company_id");

            migrationBuilder.CreateIndex(
                name: "ix_companies_tenant_id",
                schema: "app",
                table: "companies",
                column: "tenant_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "companies",
                schema: "app");

            migrationBuilder.DropIndex(
                name: "ix_workspaces_company_id",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropIndex(
                name: "ix_ontologies_company_id",
                schema: "app",
                table: "ontologies");

            migrationBuilder.DropColumn(
                name: "company_id",
                schema: "app",
                table: "workspaces");

            migrationBuilder.DropColumn(
                name: "company_id",
                schema: "app",
                table: "ontologies");
        }
    }
}
