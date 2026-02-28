namespace Geodesic.App.Api.Graph;

// --- graphSchema endpoint (spec: GraphSchema, NodeTypeInfo, PropertyInfo, RelationshipTypeInfo, SuggestedPattern) ---

public sealed class GraphSchema
{
    public IReadOnlyList<NodeTypeInfo> NodeTypes { get; set; } = Array.Empty<NodeTypeInfo>();
    public IReadOnlyList<RelationshipTypeInfo> RelationshipTypes { get; set; } = Array.Empty<RelationshipTypeInfo>();
    public IReadOnlyList<SuggestedPattern>? SuggestedPatterns { get; set; }
}

public sealed class NodeTypeInfo
{
    public string Label { get; set; } = "";
    public string? Description { get; set; }
    public int? Count { get; set; }
    public IReadOnlyList<SchemaPropertyInfo> Properties { get; set; } = Array.Empty<SchemaPropertyInfo>();
}

public sealed class SchemaPropertyInfo
{
    public string Name { get; set; } = "";
    public GraphDataType DataType { get; set; }
    public string? Description { get; set; }
    public bool IsIdentifier { get; set; }
    public IReadOnlyList<string>? ExampleValues { get; set; }
    public bool Required { get; set; }
}

public sealed class RelationshipTypeInfo
{
    public string Type { get; set; } = "";
    public string? Description { get; set; }
    public IReadOnlyList<string> FromLabels { get; set; } = Array.Empty<string>();
    public IReadOnlyList<string> ToLabels { get; set; } = Array.Empty<string>();
    public Cardinality Cardinality { get; set; }
    public IReadOnlyList<SchemaPropertyInfo>? Properties { get; set; }
}

public enum Cardinality
{
    OneToOne,
    OneToMany,
    ManyToOne,
    ManyToMany
}

public sealed class SuggestedPattern
{
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string CypherPattern { get; set; } = "";
    public string ExampleQuery { get; set; } = "";
}
