using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(AgentRole))]
public sealed class AgentRoleTypeExtensions
{
    public async Task<Ontology?> ReadOntologyAsync(
        [Parent] AgentRole role,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (role.ReadOntologyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(o => o.OntologyId == role.ReadOntologyId, ct);
    }

    public async Task<Ontology?> WriteOntologyAsync(
        [Parent] AgentRole role,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (role.WriteOntologyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(o => o.OntologyId == role.WriteOntologyId, ct);
    }

    public async Task<IReadOnlyList<Intent>> IntentsAsync(
        [Parent] AgentRole role,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var intentIds = await db.AgentRoleIntents.AsNoTracking()
            .Where(x => x.AgentRoleId == role.AgentRoleId)
            .Select(x => x.IntentId)
            .ToListAsync(ct);
        if (intentIds.Count == 0)
            return Array.Empty<Intent>();
        return await db.Intents.AsNoTracking().Where(i => intentIds.Contains(i.IntentId)).ToListAsync(ct);
    }

    public async Task<IReadOnlyList<AgentRoleAccessKey>> AccessKeysAsync(
        [Parent] AgentRole role,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.AgentRoleAccessKeys.AsNoTracking()
            .Where(x => x.AgentRoleId == role.AgentRoleId)
            .OrderByDescending(x => x.CreatedOn)
            .ToListAsync(ct);
    }
}
