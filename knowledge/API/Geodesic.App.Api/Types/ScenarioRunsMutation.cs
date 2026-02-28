using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class ScenarioRunsMutation
{
    public async Task<long> AppendScenarioRunLogAsync(
        Guid runId,
        string content,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        // Resolve tenant from claims or header; worker sets X-Tenant-Id
        var http = accessor.HttpContext;
        var tenantIdStr = http?.User?.FindFirst("tid")?.Value;
        if (string.IsNullOrWhiteSpace(tenantIdStr))
            tenantIdStr = http?.Request.Headers["X-Tenant-Id"].ToString();
        if (!Guid.TryParse(tenantIdStr, out var tenantId))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Tenant id missing or invalid for appendScenarioRunLog")
                .SetCode("TENANT_REQUIRED")
                .Build());
        }
        var log = new ScenarioRunLog
        {
            TenantId = tenantId,
            RunId = runId,
            Content = content,
            CreatedAt = DateTimeOffset.UtcNow
        };
        db.ScenarioRunLogs.Add(log);
        await db.SaveChangesAsync(ct);
        return log.LogId;
    }

    public async Task<bool> UpdateScenarioRunAsync(
        Guid runId,
        string? status,
        string? outputs,
        string? errorMessage,
        DateTimeOffset? startedAt,
        DateTimeOffset? finishedAt,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var run = await db.ScenarioRuns.FirstOrDefaultAsync(r => r.RunId == runId, ct);
        if (run is null) return false;
        if (status is not null) run.Status = status;
        if (outputs is not null) run.Outputs = outputs;
        if (errorMessage is not null) run.ErrorMessage = errorMessage;
        if (startedAt.HasValue) run.StartedAt = startedAt.Value;
        if (finishedAt.HasValue) run.FinishedAt = finishedAt.Value;
        await db.SaveChangesAsync(ct);
        return true;
    }
}

