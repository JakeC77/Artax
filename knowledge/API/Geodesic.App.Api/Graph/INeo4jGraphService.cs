namespace Geodesic.App.Api.Graph;

public interface INeo4jGraphService
{
    Task<GraphNode?> GetNodeByIdAsync(string id, CancellationToken ct = default);
    Task<GraphEdge?> GetEdgeByIdAsync(string id, CancellationToken ct = default);
    Task<GraphNode> UpsertNodeAsync(string id, string type, IReadOnlyDictionary<string, string>? properties, CancellationToken ct = default);
    Task<GraphEdge> UpsertEdgeAsync(string id, string type, string fromId, string toId, IReadOnlyDictionary<string, string>? properties, CancellationToken ct = default);
    Task<IReadOnlyList<string>> GetNodeTypesAsync(CancellationToken ct = default);
    Task<IReadOnlyList<string>> GetEdgeTypesAsync(CancellationToken ct = default);

    // New endpoints
    Task<IReadOnlyList<GraphNode>> GetNodesByTypeAsync(string type, CancellationToken ct = default);
    Task<GraphNeighborhood> GetNeighborsAsync(string id, CancellationToken ct = default);

    // Search nodes by property criteria, optionally scoped to a label (type)
    Task<IReadOnlyList<GraphNode>> SearchNodesAsync(
        IReadOnlyList<GraphPropertyMatch> criteria,
        string? type = null,
        CancellationToken ct = default);

    // Search nodes with nested filter groups and comparison operators
    Task<IReadOnlyList<GraphNode>> SearchNodesWithFiltersAsync(
        GraphFilterGroup filterGroup,
        string? type = null,
        CancellationToken ct = default);

    Task<IReadOnlyList<GraphPropertyMetadata>> GetNodePropertyMetadataAsync(string type, CancellationToken ct = default);
    Task<IReadOnlyList<string>> GetNodeRelationshipTypesAsync(string type, CancellationToken ct = default);
    Task<long> GetNodeCountAsync(string label, CancellationToken ct = default);
    Task<(IReadOnlyList<string> FromLabels, IReadOnlyList<string> ToLabels)> GetRelationshipTypeEndpointsAsync(string relationshipType, CancellationToken ct = default);

    // Execute arbitrary Cypher query (read-only, returns nodes)
    Task<IReadOnlyList<GraphNode>> ExecuteCypherQueryAsync(string cypherQuery, CancellationToken ct = default);

    /// <summary>
    /// Execute a read-only Cypher query and return row-structured results (columns + rows).
    /// Enforces limit in code. workspaceIds: optional; no-op when graph nodes/edges have no workspace key;
    /// reserved for future filtering when the data model supports it.
    /// </summary>
    Task<CypherRowResult> ExecuteCypherRowsAsync(
        string cypherQuery,
        IReadOnlyList<string>? workspaceIds,
        int limit,
        CancellationToken ct = default);

    /// <summary>
    /// Execute a read-only Cypher query with parameters and return row-structured results.
    /// Used for intent grounding execution (parameterized, no string replacement).
    /// </summary>
    Task<CypherRowResult> ExecuteCypherRowsAsync(
        string cypherQuery,
        IReadOnlyDictionary<string, object?>? parameters,
        int limit,
        CancellationToken ct = default);
}
