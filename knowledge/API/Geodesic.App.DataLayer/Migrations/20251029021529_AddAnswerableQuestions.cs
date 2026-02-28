using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddAnswerableQuestions : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "answerable_questions",
                schema: "app",
                columns: table => new
                {
                    answerable_question_id = table.Column<Guid>(type: "uuid", nullable: false),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    question = table.Column<string>(type: "text", nullable: false),
                    query = table.Column<string>(type: "text", nullable: false),
                    description = table.Column<string>(type: "text", nullable: true),
                    result_playbook = table.Column<string>(type: "text", nullable: false),
                    required_variables = table.Column<string[]>(type: "text[]", nullable: false, defaultValueSql: "'{}'::text[]")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_answerable_questions", x => x.answerable_question_id);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "answerable_questions",
                schema: "app");
        }
    }
}
