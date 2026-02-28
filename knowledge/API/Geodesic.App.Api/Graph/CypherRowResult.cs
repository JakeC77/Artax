namespace Geodesic.App.Api.Graph;

/// <summary>
/// Row-structured result of a Cypher query: column names and rows of cell values.
/// </summary>
public sealed class CypherRowResult
{
    public IReadOnlyList<string> Columns { get; set; } = Array.Empty<string>();
    public IReadOnlyList<IReadOnlyList<object?>> Rows { get; set; } = Array.Empty<IReadOnlyList<object?>>();
    public int RowCount { get; set; }
    public bool Truncated { get; set; }
}
