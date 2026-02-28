using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class FeedbackQuery
{
    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<FeedbackRequest> FeedbackRequests([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().FeedbackRequests.AsNoTracking();

    [UseProjection, UseFiltering, UseSorting]
    public IQueryable<Feedback> Feedbacks([Service] IDbContextFactory<AppDbContext> dbFactory)
        => dbFactory.CreateDbContext().Feedbacks.AsNoTracking();

    public async Task<FeedbackRequest?> GetActiveFeedbackRequestAsync(
        Guid runId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.FeedbackRequests
            .AsNoTracking()
            .Where(r => r.RunId == runId && !r.IsResolved)
            .OrderByDescending(r => r.CreatedAt)
            .FirstOrDefaultAsync(ct);
    }

    public async Task<List<Feedback>> GetFeedbackHistoryAsync(
        Guid runId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Feedbacks
            .AsNoTracking()
            .Where(f => f.RunId == runId)
            .OrderBy(f => f.Timestamp)
            .ToListAsync(ct);
    }

    public Task<FeedbackRequest?> FeedbackRequestByIdAsync(
        Guid feedbackRequestId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
        => dbFactory.CreateDbContext().FeedbackRequests.AsNoTracking()
            .FirstOrDefaultAsync(x => x.FeedbackRequestId == feedbackRequestId, ct);

    public Task<Feedback?> FeedbackByIdAsync(
        Guid feedbackId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
        => dbFactory.CreateDbContext().Feedbacks.AsNoTracking()
            .FirstOrDefaultAsync(x => x.FeedbackId == feedbackId, ct);
}

