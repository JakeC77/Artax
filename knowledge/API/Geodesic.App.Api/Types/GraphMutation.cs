using Geodesic.App.Api.Graph;
using HotChocolate;
using HotChocolate.Types;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Mutation))]
public sealed class GraphMutation
{
    public Task<GraphNode> UpsertGraphNode(
        string id,
        string type,
        IReadOnlyDictionary<string, string>? properties,
        [Service] INeo4jGraphService graph,
        CancellationToken ct)
        => graph.UpsertNodeAsync(id, type, properties, ct);

    public Task<GraphEdge> UpsertGraphEdge(
        string id,
        string type,
        string fromId,
        string toId,
        IReadOnlyDictionary<string, string>? properties,
        [Service] INeo4jGraphService graph,
        CancellationToken ct)
        => graph.UpsertEdgeAsync(id, type, fromId, toId, properties, ct);
}
