using System.Text.Json.Serialization;

namespace Geodesic.App.Api.Models;

/// <summary>
/// Payload for a workflow run. Matches the geodesic-ai WorkflowEvent schema (camelCase in JSON).
/// </summary>
public sealed class WorkflowEventPayload
{
    [JsonPropertyName("runId")]
    public Guid RunId { get; set; }

    [JsonPropertyName("tenantId")]
    public Guid TenantId { get; set; }

    [JsonPropertyName("workspaceId")]
    public Guid WorkspaceId { get; set; }

    [JsonPropertyName("scenarioId")]
    public Guid ScenarioId { get; set; }

    [JsonPropertyName("workflowId")]
    public string WorkflowId { get; set; } = default!;

    [JsonPropertyName("inputs")]
    public string? Inputs { get; set; }

    [JsonPropertyName("prompt")]
    public string? Prompt { get; set; }

    [JsonPropertyName("relatedChangesetId")]
    public Guid? RelatedChangesetId { get; set; }

    [JsonPropertyName("engine")]
    public string? Engine { get; set; }

    [JsonPropertyName("status")]
    public string? Status { get; set; }

    [JsonPropertyName("requestedAt")]
    public DateTimeOffset? RequestedAt { get; set; }
}
