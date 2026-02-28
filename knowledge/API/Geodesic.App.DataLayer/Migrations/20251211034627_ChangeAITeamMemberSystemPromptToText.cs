using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class ChangeAITeamMemberSystemPromptToText : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "system_prompt",
                schema: "app",
                table: "ai_team_members",
                type: "text",
                nullable: true,
                oldClrType: typeof(string),
                oldType: "jsonb",
                oldDefaultValueSql: "'{}'::jsonb");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<string>(
                name: "system_prompt",
                schema: "app",
                table: "ai_team_members",
                type: "jsonb",
                nullable: false,
                defaultValueSql: "'{}'::jsonb",
                oldClrType: typeof(string),
                oldType: "text",
                oldNullable: true);
        }
    }
}
