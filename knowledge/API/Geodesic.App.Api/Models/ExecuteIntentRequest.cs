namespace Geodesic.App.Api.Models;

/// <summary>
/// Request body for POST /api/agent/intents/execute.
/// </summary>
public sealed class ExecuteIntentRequest
{
    /// <summary>Operation id of the intent (e.g. "Member Auth"). Use when intentId is not provided.</summary>
    public string? OpId { get; set; }

    /// <summary>Optional exact intent id. When provided, takes precedence over opId.</summary>
    public Guid? IntentId { get; set; }

    /// <summary>Parameters for the grounding Cypher query. Keys must match $ variable names in the query (without the $).</summary>
    public Dictionary<string, object?>? Parameters { get; set; }
}
