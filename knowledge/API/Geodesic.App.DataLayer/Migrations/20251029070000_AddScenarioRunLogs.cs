using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddScenarioRunLogs : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "scenario_run_logs",
                schema: "app",
                columns: table => new
                {
                    log_id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", Npgsql.EntityFrameworkCore.PostgreSQL.Metadata.NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    tenant_id = table.Column<Guid>(type: "uuid", nullable: false),
                    run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    content = table.Column<string>(type: "text", nullable: false),
                    created_at = table.Column<DateTimeOffset>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_scenario_run_logs", x => x.log_id);
                });

            migrationBuilder.CreateIndex(
                name: "ix_scenario_run_logs_run_id",
                schema: "app",
                table: "scenario_run_logs",
                column: "run_id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "scenario_run_logs",
                schema: "app");
        }
    }
}

