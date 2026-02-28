namespace Geodesic.App.Api.Models;

/// <summary>
/// Response body for POST /api/agent/intents/execute. Mirrors CypherRowResult.
/// </summary>
public sealed class ExecuteIntentResponse
{
    public IReadOnlyList<string> Columns { get; set; } = Array.Empty<string>();
    public IReadOnlyList<IReadOnlyList<object?>> Rows { get; set; } = Array.Empty<IReadOnlyList<object?>>();
    public int RowCount { get; set; }
    public bool Truncated { get; set; }
}
