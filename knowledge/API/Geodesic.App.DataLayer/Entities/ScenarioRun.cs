
namespace Geodesic.App.DataLayer.Entities;
public class ScenarioRun
{
    public Guid RunId { get; set; }
    public Guid WorkspaceId { get; set; }
    public Guid? ScenarioId { get; set; }
    public string? Title { get; set; }
    public string? Prompt { get; set; }
    public string Engine { get; set; } = default!; // e.g., or-tools:cp-sat
    public string Inputs { get; set; } = "{}";     // jsonb
    public string? Outputs { get; set; }           // jsonb
    public string Status { get; set; } = "queued"; // queued|running|succeeded|failed|cancelled
    public string? ErrorMessage { get; set; }
    public string? ArtifactsUri { get; set; }
    public DateTimeOffset? StartedAt { get; set; }
    public DateTimeOffset? FinishedAt { get; set; }
}
