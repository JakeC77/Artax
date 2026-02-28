using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

/// <summary>
/// Per-ontology Neo4j connection info. Password is never exposed.
/// </summary>
public sealed class OntologyNeo4jConnectionType
{
    public string Uri { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
}

/// <summary>
/// Input to set per-ontology Neo4j connection. Password is encrypted at rest and never returned.
/// </summary>
public sealed class SetOntologyNeo4jConnectionInput
{
    public string Uri { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string Password { get; set; } = string.Empty;
}

[ExtendObjectType(typeof(Ontology), IgnoreProperties = new[] { nameof(Ontology.Neo4jEncryptedPassword) })]
public sealed class OntologyTypeExtensions
{
    /// <summary>
    /// Company attached to this ontology, when companyId is set; otherwise null.
    /// </summary>
    public async Task<Company?> CompanyAsync(
        [Parent] Ontology ontology,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (ontology.CompanyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Companies.AsNoTracking().FirstOrDefaultAsync(c => c.CompanyId == ontology.CompanyId, ct);
    }

    /// <summary>
    /// When set, this ontology uses its own Neo4j instance (e.g. Aura). Password is never exposed.
    /// </summary>
    public OntologyNeo4jConnectionType? Neo4jConnection([Parent] Ontology ontology)
    {
        if (string.IsNullOrWhiteSpace(ontology.Neo4jUri) || string.IsNullOrWhiteSpace(ontology.Neo4jUsername))
            return null;
        return new OntologyNeo4jConnectionType
        {
            Uri = ontology.Neo4jUri,
            Username = ontology.Neo4jUsername
        };
    }
}
