using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Intent))]
public sealed class IntentTypeExtensions
{
    /// <summary>
    /// Ontology this intent belongs to, when ontologyId is set; otherwise null. One ontology has many intents.
    /// </summary>
    public async Task<Ontology?> OntologyAsync(
        [Parent] Intent intent,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (intent.OntologyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(o => o.OntologyId == intent.OntologyId, ct);
    }
}
