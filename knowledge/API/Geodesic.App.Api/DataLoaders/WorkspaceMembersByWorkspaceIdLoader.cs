using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using GreenDonut;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.DataLoaders;

/// <summary>
/// Batches WorkspaceMember lookups across many workspace IDs to avoid N+1.
/// </summary>
public sealed class WorkspaceMembersByWorkspaceIdLoader
    : GroupedDataLoader<Guid, WorkspaceMember>
{
    private readonly IDbContextFactory<AppDbContext> _dbFactory;

    public WorkspaceMembersByWorkspaceIdLoader(
        IBatchScheduler scheduler,
        IDbContextFactory<AppDbContext> dbFactory)
        : base(scheduler)
        => _dbFactory = dbFactory;

    protected override async Task<ILookup<Guid, WorkspaceMember>> LoadGroupedBatchAsync(
        IReadOnlyList<Guid> keys,
        CancellationToken cancellationToken)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(cancellationToken);
        var rows = await db.WorkspaceMembers
            .AsNoTracking()
            .Where(wm => keys.Contains(wm.WorkspaceId))
            .ToListAsync(cancellationToken);

        return rows.ToLookup(r => r.WorkspaceId);
    }
}
