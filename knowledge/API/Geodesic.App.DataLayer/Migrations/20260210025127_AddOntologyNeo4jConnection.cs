using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddOntologyNeo4jConnection : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "processing_status",
                schema: "app",
                table: "scratchpad_attachments",
                type: "text",
                nullable: false,
                oldClrType: typeof(string),
                oldType: "text",
                oldDefaultValue: "unprocessed");

            migrationBuilder.AddColumn<string>(
                name: "neo4j_encrypted_password",
                schema: "app",
                table: "ontologies",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "neo4j_uri",
                schema: "app",
                table: "ontologies",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "neo4j_username",
                schema: "app",
                table: "ontologies",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "neo4j_encrypted_password",
                schema: "app",
                table: "ontologies");

            migrationBuilder.DropColumn(
                name: "neo4j_uri",
                schema: "app",
                table: "ontologies");

            migrationBuilder.DropColumn(
                name: "neo4j_username",
                schema: "app",
                table: "ontologies");

            migrationBuilder.AlterColumn<string>(
                name: "processing_status",
                schema: "app",
                table: "scratchpad_attachments",
                type: "text",
                nullable: false,
                defaultValue: "unprocessed",
                oldClrType: typeof(string),
                oldType: "text");
        }
    }
}
