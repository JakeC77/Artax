using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    [DbContext(typeof(AppDbContext))]
    [Migration("20260217213000_AddKeyHashUniqueIndexToAgentRoleAccessKeys")]
    public partial class AddKeyHashUniqueIndexToAgentRoleAccessKeys : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateIndex(
                name: "ix_agent_role_access_keys_key_hash",
                schema: "app",
                table: "agent_role_access_keys",
                column: "key_hash",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_agent_role_access_keys_key_hash",
                schema: "app",
                table: "agent_role_access_keys");
        }
    }
}
