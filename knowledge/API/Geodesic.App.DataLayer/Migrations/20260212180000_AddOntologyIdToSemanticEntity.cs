using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Geodesic.App.DataLayer.Migrations
{
    /// <inheritdoc />
    public partial class AddOntologyIdToSemanticEntity : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "ontology_id",
                schema: "app",
                table: "semantic_entities",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "ix_semantic_entities_ontology_id",
                schema: "app",
                table: "semantic_entities",
                column: "ontology_id");

            migrationBuilder.AddForeignKey(
                name: "fk_semantic_entities_ontologies_ontology_id",
                schema: "app",
                table: "semantic_entities",
                column: "ontology_id",
                principalSchema: "app",
                principalTable: "ontologies",
                principalColumn: "ontology_id",
                onDelete: ReferentialAction.SetNull);

            migrationBuilder.Sql(@"
CREATE UNIQUE INDEX ix_semantic_entities_ontology_id_node_label
ON app.semantic_entities (ontology_id, node_label)
WHERE ontology_id IS NOT NULL;
");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP INDEX IF EXISTS app.ix_semantic_entities_ontology_id_node_label;");

            migrationBuilder.DropForeignKey(
                name: "fk_semantic_entities_ontologies_ontology_id",
                schema: "app",
                table: "semantic_entities");

            migrationBuilder.DropIndex(
                name: "ix_semantic_entities_ontology_id",
                schema: "app",
                table: "semantic_entities");

            migrationBuilder.DropColumn(
                name: "ontology_id",
                schema: "app",
                table: "semantic_entities");
        }
    }
}
