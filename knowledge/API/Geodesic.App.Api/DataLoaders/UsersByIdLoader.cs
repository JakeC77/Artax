using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using GreenDonut;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.DataLoaders;

/// <summary>
/// Batches User lookups across many user IDs to avoid N+1 queries.
/// </summary>
public sealed class UsersByIdLoader : BatchDataLoader<Guid, User>
{
    private readonly IDbContextFactory<AppDbContext> _dbFactory;

    public UsersByIdLoader(IBatchScheduler scheduler, IDbContextFactory<AppDbContext> dbFactory)
        : base(scheduler) => _dbFactory = dbFactory;

    protected override async Task<IReadOnlyDictionary<Guid, User>> LoadBatchAsync(
        IReadOnlyList<Guid> keys,
        CancellationToken cancellationToken)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(cancellationToken);
        var rows = await db.Users.AsNoTracking()
            .Where(u => keys.Contains(u.UserId))
            .ToListAsync(cancellationToken);
        return rows.ToDictionary(x => x.UserId);
    }
}
