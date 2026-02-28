using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddFeedbackEntities : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "feedback_requests",
                schema: "app",
                columns: table => new
                {
                    feedback_request_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    task_id = table.Column<string>(type: "text", nullable: true),
                    checkpoint = table.Column<string>(type: "text", nullable: false),
                    message = table.Column<string>(type: "text", nullable: false),
                    options = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]"),
                    metadata = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    timeout_seconds = table.Column<int>(type: "integer", nullable: false, defaultValue: 300),
                    is_resolved = table.Column<bool>(type: "boolean", nullable: false, defaultValue: false),
                    resolved_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_feedback_requests", x => x.feedback_request_id);
                });

            migrationBuilder.CreateTable(
                name: "feedbacks",
                schema: "app",
                columns: table => new
                {
                    feedback_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    task_id = table.Column<string>(type: "text", nullable: true),
                    feedback_request_id = table.Column<Guid>(type: "uuid", nullable: true),
                    subtask_id = table.Column<string>(type: "text", nullable: true),
                    feedback_text = table.Column<string>(type: "text", nullable: false),
                    action = table.Column<string>(type: "text", nullable: false),
                    target = table.Column<string>(type: "jsonb", nullable: false, defaultValueSql: "'{}'::jsonb"),
                    timestamp = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    applied = table.Column<bool>(type: "boolean", nullable: false, defaultValue: false),
                    applied_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_feedbacks", x => x.feedback_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_feedback_requests_run_id_is_resolved",
                schema: "app",
                table: "feedback_requests",
                columns: new[] { "run_id", "is_resolved" });

            migrationBuilder.CreateIndex(
                name: "ix_feedbacks_run_id",
                schema: "app",
                table: "feedbacks",
                column: "run_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "feedback_requests",
                schema: "app");

            migrationBuilder.DropTable(
                name: "feedbacks",
                schema: "app");
        }
    }
}
