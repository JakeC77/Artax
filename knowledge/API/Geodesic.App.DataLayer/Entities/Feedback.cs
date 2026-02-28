namespace Geodesic.App.DataLayer.Entities;

public class Feedback
{
    public Guid FeedbackId { get; set; }
    public Guid TenantId { get; set; }
    public Guid RunId { get; set; }
    public string? TaskId { get; set; } // Optional internal task_id for mapping
    public Guid? FeedbackRequestId { get; set; } // Link to the request that triggered this feedback
    public string? SubtaskId { get; set; } // Optional subtask UUID
    public string FeedbackText { get; set; } = default!;
    public string Action { get; set; } = default!; // approve, modify, add_subtask, redirect, cancel, clarify, priority, rate_result, improve_result, record_learning
    public string Target { get; set; } = "{}"; // jsonb - stores new_description, agent_id, subtask_description, etc.
    public DateTimeOffset Timestamp { get; set; }
    public bool Applied { get; set; } = false; // True when feedback has been incorporated into workflow
    public DateTimeOffset? AppliedAt { get; set; }
}

