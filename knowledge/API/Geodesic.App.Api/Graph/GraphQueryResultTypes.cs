namespace Geodesic.App.Api.Graph;

// --- Result and metadata (spec: GraphQueryResult, QueryMetadata, etc.) ---

public sealed class GraphQueryResult
{
    public IReadOnlyList<string> Columns { get; set; } = Array.Empty<string>();
    /// <summary>Rows of cell values as strings (numbers/bools formatted as string).</summary>
    public IReadOnlyList<IReadOnlyList<string>> Rows { get; set; } = Array.Empty<IReadOnlyList<string>>();
    public int RowCount { get; set; }
    public bool Truncated { get; set; }
    public QueryMetadata Metadata { get; set; } = null!;
}

public sealed class QueryMetadata
{
    public PatternInfo Pattern { get; set; } = null!;
    public IReadOnlyList<NodeInfo> Nodes { get; set; } = Array.Empty<NodeInfo>();
    public IReadOnlyList<RelationshipInfo> Relationships { get; set; } = Array.Empty<RelationshipInfo>();
    public IReadOnlyList<ColumnInfo> ColumnDetails { get; set; } = Array.Empty<ColumnInfo>();
    public string RowGrain { get; set; } = "";
}

public sealed class PatternInfo
{
    public string Description { get; set; } = "";
    public string CypherPattern { get; set; } = "";
}

public sealed class NodeInfo
{
    public string Alias { get; set; } = "";
    public IReadOnlyList<string> Labels { get; set; } = Array.Empty<string>();
    public int PatternPosition { get; set; }
}

public sealed class RelationshipInfo
{
    public string Type { get; set; } = "";
    public string FromAlias { get; set; } = "";
    public string ToAlias { get; set; } = "";
    public RelationshipDirection Direction { get; set; }
}

public enum RelationshipDirection
{
    Outgoing,
    Incoming,
    Undirected
}

public sealed class ColumnInfo
{
    public string Name { get; set; } = "";
    public string? NodeAlias { get; set; }
    public string? Property { get; set; }
    public GraphDataType DataType { get; set; }
    public bool IsIdentifier { get; set; }
    public ColumnRole Role { get; set; }
    /// <summary>From SemanticField when matched by node label + property.</summary>
    public string? Description { get; set; }
}

public enum GraphDataType
{
    String,
    Integer,
    Float,
    Boolean,
    Date,
    Datetime,
    List,
    Map,
    Null
}

public enum ColumnRole
{
    Identifier,
    Attribute,
    Metric,
    Category,
    Timestamp,
    Computed
}
