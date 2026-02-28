using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Geodesic.App.DataLayer;

namespace Geodesic.App.DataLayer.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20251114100001_AddWorkspaceIntent")]
    public partial class AddWorkspaceIntent : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "intent",
                schema: "app",
                table: "workspaces",
                type: "text",
                nullable: true);
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "intent",
                schema: "app",
                table: "workspaces");
        }
    }
}

