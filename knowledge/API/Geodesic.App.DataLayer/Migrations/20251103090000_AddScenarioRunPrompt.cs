using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddScenarioRunPrompt : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "prompt",
                schema: "app",
                table: "scenario_runs",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "prompt",
                schema: "app",
                table: "scenario_runs");
        }
    }
}

