using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class WorkspaceNodesQuery
{
    /// <summary>
    /// List pinned workspace nodes/edges for a workspace.
    /// </summary>
    [UsePaging(IncludeTotalCount = true)]
    [UseFiltering]
    [UseSorting]
    public IQueryable<WorkspaceItem> WorkspaceNodes(
        Guid workspaceId,
        [Service] IDbContextFactory<AppDbContext> dbFactory)
    {
        var db = dbFactory.CreateDbContext();
        return db.WorkspaceItems
                 .AsNoTracking()
                 .Where(w => w.WorkspaceId == workspaceId);
    }
}
