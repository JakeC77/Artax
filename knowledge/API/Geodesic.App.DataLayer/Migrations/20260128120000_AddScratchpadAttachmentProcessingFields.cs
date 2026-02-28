using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddScratchpadAttachmentProcessingFields : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "processing_status",
                schema: "app",
                table: "scratchpad_attachments",
                type: "text",
                nullable: false,
                defaultValue: "unprocessed");

            migrationBuilder.AddColumn<string>(
                name: "processing_error",
                schema: "app",
                table: "scratchpad_attachments",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "processing_status",
                schema: "app",
                table: "scratchpad_attachments");

            migrationBuilder.DropColumn(
                name: "processing_error",
                schema: "app",
                table: "scratchpad_attachments");
        }
    }
}
