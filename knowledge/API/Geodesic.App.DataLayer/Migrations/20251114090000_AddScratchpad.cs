using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Microsoft.EntityFrameworkCore.Infrastructure;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    [DbContext(typeof(AppDbContext))]
    [Migration("20251114090000_AddScratchpad")]
    public partial class AddScratchpad : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "scratchpad_attachments",
                schema: "app",
                columns: table => new
                {
                    scratchpad_attachment_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    uri = table.Column<string>(type: "text", nullable: true),
                    file_type = table.Column<string>(type: "text", nullable: true),
                    size = table.Column<long>(type: "bigint", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scratchpad_attachments", x => x.scratchpad_attachment_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_scratchpad_attachments_workspace_id",
                schema: "app",
                table: "scratchpad_attachments",
                column: "workspace_id");

            migrationBuilder.CreateTable(
                name: "scratchpad_notes",
                schema: "app",
                columns: table => new
                {
                    scratchpad_note_id = table.Column<Guid>(type: "uuid", nullable: false),
                    workspace_id = table.Column<Guid>(type: "uuid", nullable: false),
                    title = table.Column<string>(type: "text", nullable: false),
                    text = table.Column<string>(type: "text", nullable: false),
                    created_on = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scratchpad_notes", x => x.scratchpad_note_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_scratchpad_notes_workspace_id",
                schema: "app",
                table: "scratchpad_notes",
                column: "workspace_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "scratchpad_attachments",
                schema: "app");

            migrationBuilder.DropTable(
                name: "scratchpad_notes",
                schema: "app");
        }
    }
}
