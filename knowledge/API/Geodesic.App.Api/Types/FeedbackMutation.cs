using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class FeedbackMutation
{
    public async Task<Feedback?> SubmitFeedbackAsync(
        Guid runId,
        string feedbackText,
        string action,
        string? subtaskId,
        string? targetJson,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        
        // Resolve tenant from claims or header
        var http = accessor.HttpContext;
        var tenantIdStr = http?.User?.FindFirst("tid")?.Value;
        if (string.IsNullOrWhiteSpace(tenantIdStr))
            tenantIdStr = http?.Request.Headers["X-Tenant-Id"].ToString();
        if (!Guid.TryParse(tenantIdStr, out var tenantId))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Tenant id missing or invalid for submitFeedback")
                .SetCode("TENANT_REQUIRED")
                .Build());
        }

        // Verify run exists
        var run = await db.ScenarioRuns.FirstOrDefaultAsync(r => r.RunId == runId, ct);
        if (run is null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Scenario run with id {runId} not found")
                .SetCode("RUN_NOT_FOUND")
                .Build());
        }

        // Check if run is already completed
        if (run.Status == "succeeded" || run.Status == "failed" || run.Status == "cancelled")
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Scenario run {runId} is already completed")
                .SetCode("RUN_COMPLETED")
                .Build());
        }

        // Validate action
        var validActions = new[] { "approve", "modify", "add_subtask", "redirect", "cancel", "clarify", "priority", "rate_result", "improve_result", "record_learning" };
        if (!validActions.Contains(action))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Invalid action: {action}. Valid actions are: {string.Join(", ", validActions)}")
                .SetCode("INVALID_ACTION")
                .Build());
        }

        // Find active feedback request for this run and mark it as resolved
        var activeRequest = await db.FeedbackRequests
            .FirstOrDefaultAsync(r => r.RunId == runId && !r.IsResolved, ct);
        
        Guid? feedbackRequestId = null;
        if (activeRequest is not null)
        {
            activeRequest.IsResolved = true;
            activeRequest.ResolvedAt = DateTimeOffset.UtcNow;
            feedbackRequestId = activeRequest.FeedbackRequestId;
        }

        // Create feedback
        var feedback = new Feedback
        {
            FeedbackId = Guid.NewGuid(),
            TenantId = tenantId,
            RunId = runId,
            FeedbackRequestId = feedbackRequestId,
            SubtaskId = subtaskId,
            FeedbackText = feedbackText,
            Action = action,
            Target = targetJson ?? "{}",
            Timestamp = DateTimeOffset.UtcNow,
            Applied = false
        };

        db.Feedbacks.Add(feedback);
        await db.SaveChangesAsync(ct);

        return feedback;
    }

    public async Task<bool> MarkFeedbackAppliedAsync(
        Guid feedbackId,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        var feedback = await db.Feedbacks.FirstOrDefaultAsync(f => f.FeedbackId == feedbackId, ct);
        if (feedback is null) return false;

        feedback.Applied = true;
        feedback.AppliedAt = DateTimeOffset.UtcNow;
        await db.SaveChangesAsync(ct);
        return true;
    }

    public async Task<Guid> CreateFeedbackRequestAsync(
        Guid runId,
        string checkpoint,
        string message,
        string[] options,
        string? metadataJson,
        string? taskId,
        int? timeoutSeconds,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        CancellationToken ct)
    {
        await using var db = await dbFactory.CreateDbContextAsync(ct);
        
        // Resolve tenant from claims or header
        var http = accessor.HttpContext;
        var tenantIdStr = http?.User?.FindFirst("tid")?.Value;
        if (string.IsNullOrWhiteSpace(tenantIdStr))
            tenantIdStr = http?.Request.Headers["X-Tenant-Id"].ToString();
        if (!Guid.TryParse(tenantIdStr, out var tenantId))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Tenant id missing or invalid for createFeedbackRequest")
                .SetCode("TENANT_REQUIRED")
                .Build());
        }

        // Verify run exists
        var run = await db.ScenarioRuns.FirstOrDefaultAsync(r => r.RunId == runId, ct);
        if (run is null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Scenario run with id {runId} not found")
                .SetCode("RUN_NOT_FOUND")
                .Build());
        }

        // Mark any existing active requests as resolved
        var existingRequests = await db.FeedbackRequests
            .Where(r => r.RunId == runId && !r.IsResolved)
            .ToListAsync(ct);
        foreach (var req in existingRequests)
        {
            req.IsResolved = true;
            req.ResolvedAt = DateTimeOffset.UtcNow;
        }

        // Create new feedback request
        var request = new FeedbackRequest
        {
            FeedbackRequestId = Guid.NewGuid(),
            TenantId = tenantId,
            RunId = runId,
            TaskId = taskId,
            Checkpoint = checkpoint,
            Message = message,
            Options = options ?? Array.Empty<string>(),
            Metadata = metadataJson ?? "{}",
            TimeoutSeconds = timeoutSeconds ?? 300,
            IsResolved = false,
            CreatedAt = DateTimeOffset.UtcNow
        };

        db.FeedbackRequests.Add(request);
        await db.SaveChangesAsync(ct);

        return request.FeedbackRequestId;
    }
}

