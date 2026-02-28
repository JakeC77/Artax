using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Geodesic.App.Api.DataLoaders;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Workspace))]
public sealed class WorkspaceTypeExtensions
{
    /// <summary>
    /// Company attached to this workspace, when companyId is set; otherwise null.
    /// </summary>
    public async Task<Company?> CompanyAsync(
        [Parent] Workspace ws,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (ws.CompanyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Companies.AsNoTracking().FirstOrDefaultAsync(c => c.CompanyId == ws.CompanyId, ct);
    }

    /// <summary>
    /// Ontology attached to this workspace, when ontologyId is set; otherwise null.
    /// </summary>
    public async Task<Ontology?> OntologyAsync(
        [Parent] Workspace ws,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        if (ws.OntologyId is null)
            return null;
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        return await db.Ontologies.AsNoTracking().FirstOrDefaultAsync(o => o.OntologyId == ws.OntologyId, ct);
    }

    /// <summary>
    /// Members of the workspace, resolved via DataLoader to avoid N+1 queries.
    /// </summary>
    public async Task<IEnumerable<WorkspaceMember>> MembersAsync(
        [Parent] Workspace ws,
        WorkspaceMembersByWorkspaceIdLoader loader,
        CancellationToken ct)
    {
        var items = await loader.LoadAsync(ws.WorkspaceId, ct);
        return items;
    }

    /// <summary>
    /// Resolves the owner user for the workspace via DataLoader (avoids N+1).
    /// </summary>
    public Task<User> OwnerAsync(
        [Parent] Workspace ws,
        UsersByIdLoader usersById,
        CancellationToken ct)
        => usersById.LoadAsync(ws.OwnerUserId, ct);

    /// <summary>
    /// Setup workflow status (enum mapped from workspace.State)
    /// draft = not started, setup = in progress, working/action/archived = completed
    /// </summary>
    public SetupStatus SetupStatusEnum([Parent] Workspace ws)
    {
        return ws.State switch
        {
            "draft" => SetupStatus.NotStarted,
            "setup" => SetupStatus.InProgress,
            "working" => SetupStatus.Completed,
            "action" => SetupStatus.Completed,
            "archived" => SetupStatus.Completed,
            _ => SetupStatus.NotStarted
        };
    }

    /// <summary>
    /// Setup workflow stage (enum mapped from string)
    /// </summary>
    public SetupStage? SetupStageEnum([Parent] Workspace ws)
    {
        return ws.SetupStage switch
        {
            "intent_discovery" => SetupStage.IntentDiscovery,
            "data_scoping" => SetupStage.DataScoping,
            "data_review" => SetupStage.DataReview,
            "team_building" => SetupStage.TeamBuilding,
            _ => null
        };
    }
}
