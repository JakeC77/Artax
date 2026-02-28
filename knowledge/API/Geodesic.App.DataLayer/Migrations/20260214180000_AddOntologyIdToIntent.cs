using System;
using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    [DbContext(typeof(AppDbContext))]
    [Migration("20260214180000_AddOntologyIdToIntent")]
    public partial class AddOntologyIdToIntent : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "ontology_id",
                schema: "app",
                table: "intents",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "ix_intents_ontology_id",
                schema: "app",
                table: "intents",
                column: "ontology_id");

            migrationBuilder.AddForeignKey(
                name: "fk_intents_ontologies_ontology_id",
                schema: "app",
                table: "intents",
                column: "ontology_id",
                principalSchema: "app",
                principalTable: "ontologies",
                principalColumn: "ontology_id",
                onDelete: ReferentialAction.SetNull);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "fk_intents_ontologies_ontology_id",
                schema: "app",
                table: "intents");

            migrationBuilder.DropIndex(
                name: "ix_intents_ontology_id",
                schema: "app",
                table: "intents");

            migrationBuilder.DropColumn(
                name: "ontology_id",
                schema: "app",
                table: "intents");
        }
    }
}
