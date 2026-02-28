namespace Geodesic.App.Api.Types;

/// <summary>
/// Overall status of workspace setup workflow
/// Maps from workspace.State: draft->NotStarted, setup->InProgress, working/action/archived->Completed
/// </summary>
public enum SetupStatus
{
    NotStarted,
    InProgress,
    Completed
}

/// <summary>
/// Current stage in the 4-stage setup flow
/// </summary>
public enum SetupStage
{
    IntentDiscovery,
    DataScoping,
    DataReview,
    TeamBuilding
}

/// <summary>
/// Chat message for conversational setup interactions
/// </summary>
public sealed class ChatMessageInput
{
    public string Role { get; set; } = default!; // user|assistant
    public string Content { get; set; } = default!;
}

/// <summary>
/// User-selected entity/relationship scope from data scoping recommendations
/// </summary>
public sealed class SelectedScopeInput
{
    public string EntityType { get; set; } = default!;
    public List<Guid> NodeIds { get; set; } = new();
}

/// <summary>
/// Data scope item returned from AI data scoping
/// </summary>
public sealed class DataScopeItem
{
    public string EntityType { get; set; } = default!;
    public string? Rationale { get; set; }
    public int EstimatedCount { get; set; }
    public List<Guid> NodeIds { get; set; } = new();
}

/// <summary>
/// Result for starting workspace setup (Stage 1)
/// </summary>
public sealed class SetupStartResult
{
    public Guid RunId { get; set; }
    public SetupStage Stage { get; set; }
    public string Message { get; set; } = default!;
}

/// <summary>
/// Result for stage transitions (Stage 1→2, 2→3, 3→4)
/// </summary>
public sealed class StageTransitionResult
{
    public Guid RunId { get; set; }
    public SetupStage Stage { get; set; }
    public string? PreviousArtifact { get; set; } // JSON representation of confirmed artifact
    public string? Message { get; set; }
}

/// <summary>
/// Complete status of workspace setup for resume capability
/// </summary>
public sealed class WorkspaceSetupStatus
{
    public SetupStatus Status { get; set; }
    public SetupStage? Stage { get; set; }
    public Guid? CurrentRunId { get; set; }
    public string? IntentPackage { get; set; }  // JSON
    public string? DataScope { get; set; }  // JSON
    public string? ExecutionResults { get; set; }  // JSON
    public string? TeamConfig { get; set; }  // JSON
    public DateTimeOffset? StartedAt { get; set; }
    public DateTimeOffset? CompletedAt { get; set; }
}
