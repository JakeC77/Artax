using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class WorkspaceSetupQuery
{
    /// <summary>
    /// Get the current setup status for a workspace, supporting resume capability.
    /// </summary>
    public async Task<WorkspaceSetupStatus?> WorkspaceSetupStatusAsync(
        Guid workspaceId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        var workspace = await db.Workspaces
            .AsNoTracking()
            .FirstOrDefaultAsync(w => w.WorkspaceId == workspaceId && w.TenantId == tenantId, ct);

        if (workspace == null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace not found")
                .SetCode("WORKSPACE_NOT_FOUND")
                .Build());
        }

        // Map workspace state to GraphQL SetupStatus enum
        // draft = not started setup, setup = in progress, working/action/archived = completed
        var status = workspace.State switch
        {
            "draft" => SetupStatus.NotStarted,
            "setup" => SetupStatus.InProgress,
            "working" => SetupStatus.Completed,
            "action" => SetupStatus.Completed,
            "archived" => SetupStatus.Completed,
            _ => SetupStatus.NotStarted
        };

        SetupStage? stage = workspace.SetupStage switch
        {
            "intent_discovery" => SetupStage.IntentDiscovery,
            "data_scoping" => SetupStage.DataScoping,
            "data_review" => SetupStage.DataReview,
            "team_building" => SetupStage.TeamBuilding,
            _ => null
        };

        return new WorkspaceSetupStatus
        {
            Status = status,
            Stage = stage,
            CurrentRunId = workspace.SetupRunId,
            IntentPackage = workspace.SetupIntentPackage,
            DataScope = workspace.SetupDataScope,
            ExecutionResults = workspace.SetupExecutionResults,
            TeamConfig = workspace.SetupTeamConfig,
            StartedAt = workspace.SetupStartedAt,
            CompletedAt = workspace.SetupCompletedAt
        };
    }

    // Helper to extract tenant ID with proper error handling
    private static Guid GetTenantId(IHttpContextAccessor accessor)
    {
        var http = accessor.HttpContext;
        var tenantIdStr = http?.User?.FindFirst("tid")?.Value;
        if (string.IsNullOrWhiteSpace(tenantIdStr))
            tenantIdStr = http?.Request.Headers["X-Tenant-Id"].ToString();
        if (!Guid.TryParse(tenantIdStr, out var tenantId))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Tenant ID missing or invalid")
                .SetCode("TENANT_REQUIRED")
                .Build());
        }
        return tenantId;
    }
}
