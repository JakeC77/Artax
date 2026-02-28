using HotChocolate;

namespace Geodesic.App.Api.Graph;

public sealed class GraphNode
{
    public string Id { get; set; } = string.Empty;
    public IReadOnlyList<string> Labels { get; set; } = Array.Empty<string>();
    public IReadOnlyDictionary<string, string> Properties { get; set; } =
        new Dictionary<string, string>();
}

public sealed class GraphEdge
{
    public string Id { get; set; } = string.Empty;
    public string Type { get; set; } = string.Empty;
    public string FromId { get; set; } = string.Empty;
    public string ToId { get; set; } = string.Empty;
    public IReadOnlyDictionary<string, string> Properties { get; set; } =
        new Dictionary<string, string>();
}

public sealed class GraphNeighborhood
{
    public IReadOnlyList<GraphNode> Nodes { get; set; } = Array.Empty<GraphNode>();
    public IReadOnlyList<GraphEdge> Edges { get; set; } = Array.Empty<GraphEdge>();
}

public sealed class GraphPropertyMetadata
{
    public string Name { get; set; } = string.Empty;
    public string DataType { get; set; } = string.Empty;
}

public sealed class GraphPropertyMatch
{
    public string Property { get; set; } = string.Empty;
    public string Value { get; set; } = string.Empty;
    public bool FuzzySearch { get; set; }
    public int? MaxDistance { get; set; }
    public string? Operator { get; set; } // "eq", "gt", "lt", "before", "after", "on"
}

/// <summary>
/// A filter group that combines conditions using AND/OR logic.
/// A group can contain both direct filter conditions (Filters) and nested groups (Groups).
/// All items (filters and groups) are combined using the Operator (AND/OR).
/// </summary>
public sealed class GraphFilterGroup
{
    /// <summary>
    /// The logical operator to combine all items in this group: "AND" or "OR"
    /// </summary>
    public string Operator { get; set; } = "AND";
    
    /// <summary>
    /// Direct property filter conditions (leaf nodes in the filter tree).
    /// These are combined with Groups using the Operator.
    /// </summary>
    public IReadOnlyList<GraphPropertyMatch> Filters { get; set; } = Array.Empty<GraphPropertyMatch>();
    
    /// <summary>
    /// Nested filter groups for hierarchical logic.
    /// Each nested group is wrapped in parentheses and combined with Filters using the Operator.
    /// </summary>
    public IReadOnlyList<GraphFilterGroup>? Groups { get; set; }
}
