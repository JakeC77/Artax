namespace Geodesic.App.DataLayer.Entities;

public class FeedbackRequest
{
    public Guid FeedbackRequestId { get; set; }
    public Guid TenantId { get; set; }
    public Guid RunId { get; set; }
    public string? TaskId { get; set; } // Optional internal task_id for mapping
    public string Checkpoint { get; set; } = default!; // e.g., "decomposition", "execution"
    public string Message { get; set; } = default!;
    public string[] Options { get; set; } = Array.Empty<string>(); // e.g., ["approve", "modify", "add_subtask", "cancel"]
    public string Metadata { get; set; } = "{}"; // jsonb - stores subtasks, context, etc.
    public DateTimeOffset CreatedAt { get; set; }
    public int TimeoutSeconds { get; set; } = 300; // Default 5 minutes
    public bool IsResolved { get; set; } = false; // True when feedback is received or timeout
    public DateTimeOffset? ResolvedAt { get; set; }
}

