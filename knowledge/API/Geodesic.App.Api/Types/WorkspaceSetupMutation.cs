using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using HotChocolate;
using HotChocolate.Types;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using System.Net.Http.Json;
using Geodesic.App.Api.Messaging;
using Geodesic.App.Api.Models;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class WorkspaceSetupMutation
{
    /// <summary>
    /// Stage 1: Initialize workspace setup flow
    /// Idempotent - returns existing run if setup is already in progress
    /// Optional initialMessage allows user to start conversation immediately
    /// </summary>
    public async Task<SetupStartResult> StartWorkspaceSetupAsync(
        Guid workspaceId,
        string? initialMessage,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] IServiceProvider serviceProvider,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Validate workspace exists and belongs to tenant
        var workspace = await db.Workspaces
            .FirstOrDefaultAsync(w => w.WorkspaceId == workspaceId && w.TenantId == tenantId, ct);

        if (workspace == null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace not found")
                .SetCode("WORKSPACE_NOT_FOUND")
                .Build());
        }

        // IDEMPOTENT CHECK: If setup is already in progress and has a current run, return it
        if (workspace.State == "setup" && workspace.SetupRunId.HasValue)
        {
            // Verify the run still exists
            var existingRun = await db.ScenarioRuns
                .FirstOrDefaultAsync(r => r.RunId == workspace.SetupRunId.Value, ct);

            if (existingRun != null && (existingRun.Status == "queued" || existingRun.Status == "running"))
            {
                logger.LogInformation("Setup already in progress for workspace {WorkspaceId}, returning existing run {RunId}",
                    workspaceId, existingRun.RunId);

                return new SetupStartResult
                {
                    RunId = existingRun.RunId,
                    Stage = SetupStage.IntentDiscovery,
                    Message = "Setup already in progress. Continue your conversation with Theo."
                };
            }
        }

        // Initialize/Reset workspace setup fields
        // Transition from draft -> setup
        workspace.State = "setup";
        workspace.SetupStage = "intent_discovery";
        workspace.SetupIntentPackage = null;
        workspace.SetupDataScope = null;
        workspace.SetupExecutionResults = null;
        workspace.SetupTeamConfig = null;
        workspace.SetupStartedAt = DateTimeOffset.UtcNow;
        workspace.SetupCompletedAt = null;

        // Create a ScenarioRun for tracking this setup workflow
        var run = new ScenarioRun
        {
            RunId = Guid.NewGuid(),
            WorkspaceId = workspaceId,
            ScenarioId = null,
            Title = $"Workspace Setup: {workspace.Name}",
            Engine = "workspace_setup",
            Inputs = JsonSerializer.Serialize(new {
                workspaceId,
                stage = "intent_discovery",
                initialMessage = initialMessage // Include initial message if provided
            }),
            Status = "queued",
            StartedAt = DateTimeOffset.UtcNow
        };
        db.ScenarioRuns.Add(run);

        // Save the current run ID for resume capability
        workspace.SetupRunId = run.RunId;

        await db.SaveChangesAsync(ct);

        // Log initial user_message event - this IS the setup_started signal
        // Worker sees user_message and begins processing
        // Only log if there's an actual initial message from the user
        if (!string.IsNullOrWhiteSpace(initialMessage))
        {
            await LogEventAsync(db, tenantId, run.RunId, "user_message", new
            {
                workspaceId,
                stage = "intent_discovery",
                message = initialMessage
            }, ct);
        }

        // Trigger workflow (dispatcher in production, HTTP in local dev)
        await TriggerWorkflowAsync(
            run.RunId,
            workspaceId,
            tenantId,
            null, // scenarioId
            "workspace_setup",
            run.Inputs,
            dispatcher,
            serviceProvider,
            logger,
            ct);

        logger.LogInformation("Workspace setup started. WorkspaceId={WorkspaceId}, RunId={RunId}", workspaceId, run.RunId);

        return new SetupStartResult
        {
            RunId = run.RunId,
            Stage = SetupStage.IntentDiscovery,
            Message = "Welcome! Let's set up your workspace. What would you like to analyze or understand about your data?"
        };
    }

    /// <summary>
    /// Send message during setup conversation (any stage with chat)
    /// Logs user message to scenario_run_logs - worker's EventStreamReader picks it up
    /// Same RunId is maintained - no new runs created
    /// </summary>
    public async Task<ConversationPayload> SendSetupMessageAsync(
        Guid workspaceId,
        string message,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Validate workspace exists and setup is in progress
        var workspace = await db.Workspaces
            .FirstOrDefaultAsync(w => w.WorkspaceId == workspaceId && w.TenantId == tenantId, ct);

        if (workspace == null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace not found")
                .SetCode("WORKSPACE_NOT_FOUND")
                .Build());
        }

        if (workspace.State != "setup")
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace setup is not in progress")
                .SetCode("SETUP_NOT_IN_PROGRESS")
                .Build());
        }

        // Validate we have an active run
        if (!workspace.SetupRunId.HasValue)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("No active setup run found")
                .SetCode("NO_ACTIVE_RUN")
                .Build());
        }

        var runId = workspace.SetupRunId.Value;

        // Log user message to scenario_run_logs
        // Worker's EventStreamReader will pick this up automatically
        await LogEventAsync(db, tenantId, runId, "user_message", new
        {
            workspaceId,
            stage = workspace.SetupStage,
            message
        }, ct);

        logger.LogInformation(
            "Setup message sent. WorkspaceId={WorkspaceId}, RunId={RunId}, Stage={Stage}",
            workspaceId, runId, workspace.SetupStage);

        // Note: The actual AI response will come through the worker -> scenario_run_logs via SSE
        return new ConversationPayload
        {
            RunId = runId, // Same RunId
            AssistantMessage = "Processing your message...",
            IsComplete = false,
            NextStage = null
        };
    }

    /// <summary>
    /// Stage 1→2: Confirm intent package and transition to data scoping
    /// Saves intent package to DB and logs transition to scenario_run_logs
    /// Same RunId is maintained throughout the entire setup flow
    /// </summary>
    public async Task<StageTransitionResult> ConfirmIntentAndStartDataScopingAsync(
        Guid workspaceId,
        string intentPackage,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Validate workspace and stage
        var workspace = await ValidateWorkspaceAndStageAsync(db, workspaceId, tenantId, "intent_discovery", ct);

        // Validate intent package is provided
        if (string.IsNullOrWhiteSpace(intentPackage))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Intent package is required")
                .SetCode("INTENT_PACKAGE_REQUIRED")
                .Build());
        }

        // Validate we have an active run
        if (!workspace.SetupRunId.HasValue)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("No active setup run found")
                .SetCode("NO_ACTIVE_RUN")
                .Build());
        }

        var runId = workspace.SetupRunId.Value;

        // CRITICAL: Save intent package to database for persistence/resume
        workspace.SetupIntentPackage = intentPackage;
        workspace.SetupStage = "data_scoping";

        // Extract description from intent package and update workspace
        try
        {
            var intentDoc = JsonSerializer.Deserialize<JsonElement>(intentPackage);
            if (intentDoc.TryGetProperty("description", out var descProp))
            {
                workspace.Description = descProp.GetString();
            }
        }
        catch (JsonException ex)
        {
            logger.LogWarning(ex, "Failed to parse intent package for description extraction");
        }

        await db.SaveChangesAsync(ct);

        // Log transition event to scenario_run_logs
        // Worker's EventStreamReader will pick this up automatically
        await LogEventAsync(db, tenantId, runId, "end_intent", new
        {
            workspaceId,
            previousStage = "intent_discovery",
            newStage = "data_scoping",
            intent_package = intentPackage,
            message = "Intent confirmed. Transitioning to data scoping stage."
        }, ct);

        logger.LogInformation(
            "Intent confirmed, transitioning to data scoping. WorkspaceId={WorkspaceId}, RunId={RunId}",
            workspaceId, runId);

        return new StageTransitionResult
        {
            RunId = runId, // Same RunId - no new run created
            Stage = SetupStage.DataScoping,
            PreviousArtifact = intentPackage,
            Message = "Great! Now let's identify the data entities and relationships you need."
        };
    }

    /// <summary>
    /// Stage 2→3: Confirm data scope and transition to data review/execution
    /// Saves data scope to DB and logs transition to scenario_run_logs
    /// Same RunId is maintained throughout the entire setup flow
    /// </summary>
    public async Task<StageTransitionResult> ConfirmDataScopeAndStartExecutionAsync(
        Guid workspaceId,
        string dataScope,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Validate workspace and stage
        var workspace = await ValidateWorkspaceAndStageAsync(db, workspaceId, tenantId, "data_scoping", ct);

        // Validate data scope is provided
        if (string.IsNullOrWhiteSpace(dataScope))
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Data scope is required")
                .SetCode("DATA_SCOPE_REQUIRED")
                .Build());
        }

        // Validate we have an active run
        if (!workspace.SetupRunId.HasValue)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("No active setup run found")
                .SetCode("NO_ACTIVE_RUN")
                .Build());
        }

        var runId = workspace.SetupRunId.Value;

        // CRITICAL: Save data scope to database for persistence/resume
        workspace.SetupDataScope = dataScope;
        workspace.SetupStage = "data_review";
        await db.SaveChangesAsync(ct);

        // Log transition event to scenario_run_logs
        // Worker's EventStreamReader will pick this up automatically
        await LogEventAsync(db, tenantId, runId, "end_data_scoping", new
        {
            workspaceId,
            previousStage = "data_scoping",
            newStage = "data_review",
            data_scope = dataScope,
            message = "Data scope confirmed. Transitioning to data review stage."
        }, ct);

        logger.LogInformation(
            "Data scope confirmed, transitioning to data review. WorkspaceId={WorkspaceId}, RunId={RunId}",
            workspaceId, runId);

        return new StageTransitionResult
        {
            RunId = runId, // Same RunId - no new run created
            Stage = SetupStage.DataReview,
            PreviousArtifact = dataScope,
            Message = "Data scope confirmed. The system is now gathering and preparing your data."
        };
    }

    /// <summary>
    /// Stage 3→4: Confirm reviewed data and transition to team building
    /// Saves execution results, creates workspace items, and logs transition to scenario_run_logs
    /// Same RunId is maintained throughout the entire setup flow
    /// </summary>
    public async Task<StageTransitionResult> ConfirmDataReviewAndBuildTeamAsync(
        Guid workspaceId,
        string executionResults,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        // Start transaction for atomic operations
        await using var transaction = await db.Database.BeginTransactionAsync(ct);

        try
        {
            // Validate workspace and stage
            var workspace = await ValidateWorkspaceAndStageAsync(db, workspaceId, tenantId, "data_review", ct);

            // Validate executionResults is provided
            if (string.IsNullOrWhiteSpace(executionResults))
            {
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Execution results are required")
                    .SetCode("EXECUTION_RESULTS_REQUIRED")
                    .Build());
            }

            // Parse execution results to extract node IDs with their entity types (labels)
            List<ExecutionResultItem>? executionData;
            try
            {
                executionData = JsonSerializer.Deserialize<List<ExecutionResultItem>>(executionResults);
            }
            catch (JsonException ex)
            {
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage($"Invalid execution results format: {ex.Message}")
                    .SetCode("INVALID_EXECUTION_RESULTS")
                    .Build());
            }

            if (executionData == null || !executionData.Any() || !executionData.Any(r => r.NodeIds.Any()))
            {
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("At least one node must be selected in execution results")
                    .SetCode("NO_NODES_SELECTED")
                    .Build());
            }

            // Validate we have an active run
            if (!workspace.SetupRunId.HasValue)
            {
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("No active setup run found")
                    .SetCode("NO_ACTIVE_RUN")
                    .Build());
            }

            var runId = workspace.SetupRunId.Value;

            // CRITICAL: Save execution results to database for persistence/resume
            workspace.SetupExecutionResults = executionResults;
            workspace.SetupStage = "team_building";

            // Create workspace items with labels from execution results
            var workspaceItems = new List<WorkspaceItem>();
            var allNodeIds = new List<string>();
            foreach (var result in executionData)
            {
                foreach (var nodeId in result.NodeIds)
                {
                    var item = new WorkspaceItem
                    {
                        WorkspaceItemId = Guid.NewGuid(),
                        WorkspaceId = workspaceId,
                        GraphNodeId = nodeId,
                        GraphEdgeId = null,
                        Labels = new string[] { result.EntityType },
                        PinnedBy = Guid.Empty, // System-added during setup
                        PinnedAt = DateTimeOffset.UtcNow
                    };
                    workspaceItems.Add(item);
                    allNodeIds.Add(nodeId);
                }
            }

            db.WorkspaceItems.AddRange(workspaceItems);
            await db.SaveChangesAsync(ct);

            // Log team building started event to scenario_run_logs
            // Worker's EventStreamReader will pick this up automatically
            await LogEventAsync(db, tenantId, runId, "end_data_review", new
            {
                workspaceId,
                previousStage = "data_review",
                newStage = "team_building",
                execution_results = executionResults,
                selectedNodeCount = allNodeIds.Count,
                workspaceItemCount = workspaceItems.Count,
                selected_node_ids = allNodeIds,
                message = "Data review confirmed. Transitioning to team building stage."
            }, ct);

            // Commit the transaction
            await transaction.CommitAsync(ct);

            logger.LogInformation(
                "Data review confirmed, transitioning to team building. WorkspaceId={WorkspaceId}, RunId={RunId}, WorkspaceItems={Count}",
                workspaceId, runId, workspaceItems.Count);

            return new StageTransitionResult
            {
                RunId = runId, // Same RunId - no new run created
                Stage = SetupStage.TeamBuilding,
                Message = $"Building your AI team... {workspaceItems.Count} workspace items created."
            };
        }
        catch (Exception ex)
        {
            // Rollback transaction on error
            await transaction.RollbackAsync(ct);

            logger.LogError(ex, "confirmDataReviewAndBuildTeam failed for workspaceId={WorkspaceId}", workspaceId);

            // Don't revert state - keep workspace in current state, only move forward
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Team building failed: {ex.Message}")
                .SetCode("TEAM_BUILDING_FAILED")
                .Build());
        }
    }

    /// <summary>
    /// Complete workspace setup - Called by AI worker after team_builder workflow completes
    /// Updates workspace status to completed, then triggers the initial analysis workflow
    /// Returns the new analysis run_id so frontend can subscribe to SSE stream
    /// Returns null if setup was already completed (idempotency)
    /// </summary>
    public async Task<Guid?> CompleteWorkspaceSetupAsync(
        Guid workspaceId,
        string? teamConfig,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<WorkspaceSetupMutation> logger,
        [Service] IWorkflowDispatcher dispatcher,
        [Service] IServiceProvider serviceProvider,
        CancellationToken ct)
    {
        var tenantId = GetTenantId(accessor);
        await using var db = await dbFactory.CreateDbContextAsync(ct);

        try
        {
            // Validate workspace exists and belongs to tenant
            var workspace = await db.Workspaces
                .FirstOrDefaultAsync(w => w.WorkspaceId == workspaceId && w.TenantId == tenantId, ct);

            if (workspace == null)
            {
                throw new GraphQLException(ErrorBuilder.New()
                    .SetMessage("Workspace not found")
                    .SetCode("WORKSPACE_NOT_FOUND")
                    .Build());
            }

            // Idempotency: If workspace is already in "working" state with SetupCompletedAt set, skip
            if (workspace.State == "working" && workspace.SetupCompletedAt.HasValue)
            {
                logger.LogInformation(
                    "Workspace setup already completed. WorkspaceId={WorkspaceId}, CompletedAt={CompletedAt}",
                    workspaceId, workspace.SetupCompletedAt);
                return null; // Already completed, no new run created
            }

            // Save team_config to workspace if provided (for reference)
            if (!string.IsNullOrWhiteSpace(teamConfig))
            {
                workspace.SetupTeamConfig = teamConfig;
            }

            // Update workspace state to working (setup complete)
            // Note: AITeam and AITeamMember records are created by the Python worker
            // Keep SetupRunId - it references the setup conversation history in scenario_run_logs
            workspace.State = "working";
            workspace.SetupCompletedAt = DateTimeOffset.UtcNow;

            await db.SaveChangesAsync(ct);

            // Create a new ScenarioRun for the analysis workflow
            var analysisRun = new ScenarioRun
            {
                RunId = Guid.NewGuid(),
                WorkspaceId = workspaceId,
                ScenarioId = null,
                Title = $"Initial Analysis: {workspace.Name}",
                Engine = "ai:workspace-analyzer",
                Inputs = JsonSerializer.Serialize(new
                {
                    intent_package = workspace.SetupIntentPackage,
                    parent_run_id = workspace.SetupRunId
                }),
                Status = "queued",
                StartedAt = DateTimeOffset.UtcNow
            };
            db.ScenarioRuns.Add(analysisRun);
            await db.SaveChangesAsync(ct);

            // Trigger the analysis workflow
            await TriggerWorkflowAsync(
                analysisRun.RunId,
                workspaceId,
                tenantId,
                null, // scenarioId
                "ai:workspace-analyzer",
                analysisRun.Inputs,
                dispatcher,
                serviceProvider,
                logger,
                ct);

            logger.LogInformation(
                "Workspace setup completed and analysis workflow triggered. WorkspaceId={WorkspaceId}, AnalysisRunId={AnalysisRunId}",
                workspaceId, analysisRun.RunId);

            return analysisRun.RunId;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "completeWorkspaceSetup failed for workspaceId={WorkspaceId}", workspaceId);

            // Don't revert state - keep workspace in current state, only move forward
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Setup completion failed: {ex.Message}")
                .SetCode("SETUP_COMPLETION_FAILED")
                .Build());
        }
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

    // Helper to validate workspace exists, belongs to tenant, and is in expected stage
    private static async Task<Workspace> ValidateWorkspaceAndStageAsync(
        AppDbContext db,
        Guid workspaceId,
        Guid tenantId,
        string expectedStage,
        CancellationToken ct)
    {
        var workspace = await db.Workspaces
            .FirstOrDefaultAsync(w => w.WorkspaceId == workspaceId && w.TenantId == tenantId, ct);

        if (workspace == null)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Workspace not found")
                .SetCode("WORKSPACE_NOT_FOUND")
                .Build());
        }

        if (workspace.SetupStage != expectedStage)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage($"Invalid setup stage. Expected '{expectedStage}', but workspace is in '{workspace.SetupStage}' stage.")
                .SetCode("INVALID_STAGE")
                .Build());
        }

        return workspace;
    }

    // Helper to log events to scenario_run_logs
    // For user_message events, message goes at top level AND in data
    private static async Task LogEventAsync(
        AppDbContext db,
        Guid tenantId,
        Guid runId,
        string eventType,
        object eventData,
        CancellationToken ct)
    {
        string content;

        if (eventType == "user_message")
        {
            // user_message format: { event_type, message, data, timestamp }
            // Message at top level for worker, data for full context
            var dict = JsonSerializer.Deserialize<Dictionary<string, object>>(
                JsonSerializer.Serialize(eventData));
            var message = dict?.GetValueOrDefault("message")?.ToString() ?? "";

            content = JsonSerializer.Serialize(new
            {
                event_type = eventType,
                message = message,
                data = eventData,
                timestamp = DateTimeOffset.UtcNow
            });
        }
        else
        {
            // Other events: nest data under "data" key
            content = JsonSerializer.Serialize(new
            {
                event_type = eventType,
                data = eventData,
                timestamp = DateTimeOffset.UtcNow
            });
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
    }

    // ========================================================================
    // LOCAL DEV ONLY - COMMENT OUT FOR PRODUCTION
    // This helper enables local development workflow testing without Azure Service Bus
    // Set environment variables:
    //   LOCAL_DEV_MODE=true
    //   LOCAL_AI_WORKER_URL=http://localhost:8000
    // ========================================================================
    private static async Task TriggerWorkflowAsync(
        Guid runId,
        Guid workspaceId,
        Guid tenantId,
        Guid? scenarioId,
        string engine,
        string inputs,
        IWorkflowDispatcher dispatcher,
        IServiceProvider serviceProvider,
        ILogger<WorkspaceSetupMutation> logger,
        CancellationToken ct)
    {
        // ========== LOCAL DEV MODE - START ==========
        // COMMENT OUT THIS ENTIRE BLOCK FOR PRODUCTION
        var localMode = Environment.GetEnvironmentVariable("LOCAL_DEV_MODE")?.ToLowerInvariant() == "true";

        if (localMode)
        {
            logger.LogInformation("LOCAL DEV MODE: Triggering workflow via HTTP instead of dispatcher");

            var workerUrl = Environment.GetEnvironmentVariable("LOCAL_AI_WORKER_URL") ?? "http://localhost:8000";
            var httpClientFactory = serviceProvider.GetRequiredService<IHttpClientFactory>();
            var httpClient = httpClientFactory.CreateClient();

            var payload = new
            {
                tenant_id = tenantId.ToString(),
                workspace_id = workspaceId.ToString(),
                scenario_id = scenarioId?.ToString() ?? "00000000-0000-0000-0000-000000000000",
                run_id = runId.ToString(),
                inputs = JsonSerializer.Deserialize<object>(inputs) // Parse inputs JSON
            };

            try
            {
                var endpoint = $"{workerUrl.TrimEnd('/')}/api/workflows/{engine}/trigger";
                logger.LogInformation("LOCAL DEV: POST {Endpoint}", endpoint);

                var response = await httpClient.PostAsJsonAsync(endpoint, payload, ct);

                if (response.IsSuccessStatusCode)
                {
                    var result = await response.Content.ReadAsStringAsync(ct);
                    logger.LogInformation(
                        "LOCAL DEV: Workflow triggered successfully. " +
                        "RunId={RunId}, Engine={Engine}, Response={Response}",
                        runId, engine, result);
                }
                else
                {
                    var error = await response.Content.ReadAsStringAsync(ct);
                    logger.LogError(
                        "LOCAL DEV: Failed to trigger workflow. " +
                        "RunId={RunId}, Engine={Engine}, Status={StatusCode}, Error={Error}",
                        runId, engine, (int)response.StatusCode, error);
                }
            }
            catch (Exception ex)
            {
                logger.LogError(ex,
                    "LOCAL DEV: Exception triggering workflow via HTTP. " +
                    "RunId={RunId}, Engine={Engine}, WorkerUrl={WorkerUrl}",
                    runId, engine, workerUrl);
            }

            return; // Exit early - don't use dispatcher in local dev mode
        }
        // ========== LOCAL DEV MODE - END ==========

        var workflowPayload = new WorkflowEventPayload
        {
            RunId = runId,
            TenantId = tenantId,
            WorkspaceId = workspaceId,
            ScenarioId = scenarioId ?? Guid.Empty,
            WorkflowId = engine,
            Engine = engine,
            Inputs = inputs,
            Status = "queued",
            RequestedAt = DateTimeOffset.UtcNow
        };
        try
        {
            var dispatched = await dispatcher.DispatchAsync(workflowPayload, ct);
            if (dispatched)
                logger.LogInformation("Workflow dispatched. RunId={RunId}, Engine={Engine}", runId, engine);
            else
                logger.LogWarning("Workflow dispatcher did not send. RunId={RunId}, Engine={Engine}", runId, engine);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to dispatch workflow. RunId={RunId}, Engine={Engine}", runId, engine);
        }
    }
}

/// <summary>
/// Response for workspace setup state mutations
/// </summary>
public sealed class WorkspaceSetupPayload
{
    public Guid WorkspaceId { get; set; }
    public string State { get; set; } = default!; // draft|setup|working|action|archived
    public string SetupStage { get; set; } = default!;
    public Guid RunId { get; set; }
    public string? Message { get; set; }
}

/// <summary>
/// Response for conversational mutations
/// </summary>
public sealed class ConversationPayload
{
    public Guid RunId { get; set; }
    public string AssistantMessage { get; set; } = default!;
    public bool IsComplete { get; set; }
    public string? NextStage { get; set; }
}

/// <summary>
/// Response for data review stage with scopes
/// </summary>
public sealed class DataReviewPayload
{
    public Guid WorkspaceId { get; set; }
    public string State { get; set; } = default!; // draft|setup|working|action|archived
    public string SetupStage { get; set; } = default!;
    public List<DataScopeItem> Scopes { get; set; } = new();
    public string? Message { get; set; }
}

/// <summary>
/// Deserialization helper for execution results from data review stage
/// </summary>
internal sealed class ExecutionResultItem
{
    [System.Text.Json.Serialization.JsonPropertyName("entity_type")]
    public string EntityType { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("node_ids")]
    public List<string> NodeIds { get; set; } = new();
}
