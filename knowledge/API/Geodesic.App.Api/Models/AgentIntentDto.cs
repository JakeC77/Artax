namespace Geodesic.App.Api.Models;

/// <summary>
/// Intent payload returned by the agent intents API (GET /api/agent/intents).
/// CamelCase in JSON.
/// </summary>
public sealed class AgentIntentDto
{
    public Guid IntentId { get; set; }
    public string OpId { get; set; } = string.Empty;
    public string IntentName { get; set; } = string.Empty;
    public string? Route { get; set; }
    public string? Description { get; set; }
    public string? DataSource { get; set; }
    public string? InputSchema { get; set; }
    public string? OutputSchema { get; set; }
    public string? Grounding { get; set; }
    public Guid? OntologyId { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public DateTimeOffset? LastEdit { get; set; }
}
