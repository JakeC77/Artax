using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class WorkspaceNodesMutation
{
    /// <summary>
    /// Add (pin) a graph node/edge to a workspace with optional labels.
    /// Idempotent on (workspaceId, graphNodeId, graphEdgeId).
    /// </summary>
    public async Task<WorkspaceItem> AddWorkspaceNodeAsync(
        Guid workspaceId,
        string graphNodeId,
        string? graphEdgeId,
        string[]? labels,
        Guid pinnedBy,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        var existing = await db.WorkspaceItems
            .FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId
                                   && x.GraphNodeId == graphNodeId
                                   && x.GraphEdgeId == graphEdgeId, ct);
        if (existing is not null)
        {
            if (labels is not null && labels.Length > 0)
                existing.Labels = labels;
            existing.PinnedBy = pinnedBy;
            await db.SaveChangesAsync(ct);
            return existing;
        }

        var item = new WorkspaceItem
        {
            WorkspaceId = workspaceId,
            GraphNodeId = graphNodeId,
            GraphEdgeId = graphEdgeId,
            Labels = labels ?? Array.Empty<string>(),
            PinnedBy = pinnedBy,
            PinnedAt = DateTimeOffset.UtcNow
        };
        db.WorkspaceItems.Add(item);
        await db.SaveChangesAsync(ct);
        return item;
    }

    /// <summary>
    /// Update labels on a pinned workspace node/edge.
    /// </summary>
    public async Task<WorkspaceItem?> UpdateWorkspaceNodeLabelsAsync(
        Guid workspaceId,
        string graphNodeId,
        string? graphEdgeId,
        string[] labels,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var item = await db.WorkspaceItems
            .FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId
                                   && x.GraphNodeId == graphNodeId
                                   && x.GraphEdgeId == graphEdgeId, ct);
        if (item is null) return null;
        item.Labels = labels ?? Array.Empty<string>();
        await db.SaveChangesAsync(ct);
        return item;
    }

    /// <summary>
    /// Remove (unpin) a graph node/edge from a workspace.
    /// </summary>
    public async Task<bool> RemoveWorkspaceNodeAsync(
        Guid workspaceId,
        string graphNodeId,
        string? graphEdgeId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var item = await db.WorkspaceItems
            .FirstOrDefaultAsync(x => x.WorkspaceId == workspaceId
                                   && x.GraphNodeId == graphNodeId
                                   && x.GraphEdgeId == graphEdgeId, ct);
        if (item is null) return false;
        db.WorkspaceItems.Remove(item);
        await db.SaveChangesAsync(ct);
        return true;
    }
}
