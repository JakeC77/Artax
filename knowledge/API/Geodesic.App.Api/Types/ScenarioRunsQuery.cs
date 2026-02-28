using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class ScenarioRunsQuery
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<ScenarioRunLog> ScenarioRunLogs([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().ScenarioRunLogs.AsNoTracking();

    /// <param name="withinDays">Optional. When set, only return logs with CreatedAt >= UtcNow - withinDays.</param>
    public async Task<List<ScenarioRunLog>> GetScenarioRunLogsByRunIdAsync(
        Guid runId,
        int? withinDays,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var cutoff = withinDays.HasValue ? DateTimeOffset.UtcNow.AddDays(-withinDays.Value) : (DateTimeOffset?)null;
        var query = db.ScenarioRunLogs
            .AsNoTracking()
            .Where(x => x.RunId == runId);
        if (cutoff.HasValue)
            query = query.Where(x => x.CreatedAt >= cutoff.Value);
        return await query
            .OrderBy(x => x.LogId)
            .ToListAsync(ct);
    }
}

