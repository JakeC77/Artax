using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddDataTypeToSemanticField : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "data_type",
                schema: "app",
                table: "semantic_fields",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "data_type",
                schema: "app",
                table: "semantic_fields");
        }
    }
}
