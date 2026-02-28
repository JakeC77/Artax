using Geodesic.App.Api.Graph;
using Geodesic.App.DataLayer;
using Microsoft.EntityFrameworkCore;
using HotChocolate;
using HotChocolate.Types;
using Neo4j.Driver;

namespace Geodesic.App.Api.Types;

[ExtendObjectType(typeof(Query))]
public sealed class GraphQuery
{
    public async Task<GraphNode?> GraphNodeById(
        string id,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetNodeByIdAsync(id, ct);
    }

    public Task<GraphEdge?> GraphEdgeById(
        string id,
        [Service] INeo4jGraphService graph)
        => graph.GetEdgeByIdAsync(id);

    public async Task<IReadOnlyList<string>> GraphNodeTypes(
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetNodeTypesAsync(ct);
    }

    public async Task<IReadOnlyList<string>> GraphEdgeTypes(
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetEdgeTypesAsync(ct);
    }

    public async Task<IReadOnlyList<GraphNode>> GraphNodesByType(
        string type,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetNodesByTypeAsync(type, ct);
    }

    public Task<GraphNeighborhood> GraphNeighbors(
        string id,
        [Service] INeo4jGraphService graph)
        => graph.GetNeighborsAsync(id);

    public async Task<IReadOnlyList<GraphNode>> GraphNodesSearch(
        IReadOnlyList<GraphPropertyMatch> criteria,
        string? type,
        Guid? ontologyId,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken cancellationToken)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, ontologyId, dbFactory, neo4jFactory, graph, cancellationToken);
        return await service.SearchNodesAsync(criteria, type, cancellationToken);
    }

    public async Task<IReadOnlyList<GraphNode>> GraphNodesSearchWithFilters(
        GraphFilterGroup filterGroup,
        string? type,
        Guid? ontologyId,
        [Service] INeo4jGraphService graph,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken cancellationToken)
    {
        var service = ontologyId.HasValue
            ? await neo4jFactory.GetGraphServiceForOntologyAsync(ontologyId.Value, cancellationToken)
            : graph;
        return await service.SearchNodesWithFiltersAsync(filterGroup, type, cancellationToken);
    }

    public async Task<IReadOnlyList<GraphPropertyMetadata>> GraphNodePropertyMetadata(
        string type,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetNodePropertyMetadataAsync(type, ct);
    }

    public async Task<IReadOnlyList<string>> GraphNodeRelationshipTypes(
        string type,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        CancellationToken ct)
    {
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
        return await service.GetNodeRelationshipTypesAsync(type, ct);
    }

    public async Task<IReadOnlyList<GraphNode>> GraphNodesByCypher(
        string cypherQuery,
        Guid? workspaceId,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        [Service] ILogger<GraphQuery> logger,
        CancellationToken ct)
    {
        try
        {
            var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, ct);
            return await service.ExecuteCypherQueryAsync(cypherQuery, ct);
        }
        catch (ArgumentException ex)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage(ex.Message)
                .SetCode("CYPHER_VALIDATION")
                .Build());
        }
        catch (ClientException ex)
        {
            logger.LogWarning(ex, "Neo4j client error executing Cypher: {Code} {Message}", ex.Code, ex.Message);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Cypher execution failed: " + ex.Message)
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
        catch (Neo4jException ex)
        {
            logger.LogWarning(ex, "Neo4j error executing Cypher: {Message}", ex.Message);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Graph database error: " + ex.Message)
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unexpected error executing Cypher query");
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Cypher execution failed. See server logs for details.")
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
    }

    /// <summary>
    /// Execute a Cypher query and return row-structured results with metadata.
    /// workspaceIds is optional (no-op if graph has no workspace key).
    /// </summary>
    public async Task<GraphQueryResult> GraphRowsByCypher(
        string cypherQuery,
        IReadOnlyList<string>? workspaceIds,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] IHttpContextAccessor accessor,
        [Service] ILogger<GraphQuery> logger,
        CancellationToken cancellationToken,
        int limit = 10000)
    {
        try
        {
            var rowResult = await graph.ExecuteCypherRowsAsync(cypherQuery, workspaceIds, limit, cancellationToken);
            var (pattern, nodes, relationships, columnDetailsList, rowGrain) = CypherMetadataParser.Parse(cypherQuery, rowResult.Columns.ToList());
            var columnDetails = columnDetailsList.ToList();

            if (rowResult.Rows.Count > 0)
            {
                var firstRow = rowResult.Rows[0];
                MetadataEnricher.EnrichFromFirstRow(columnDetails, firstRow);
            }

            await using var db = await dbFactory.CreateDbContextAsync(cancellationToken);
            var tenantId = ResolveTenantId(accessor);
            var semanticEntities = tenantId != Guid.Empty
                ? await db.SemanticEntities.AsNoTracking()
                    .Include(e => e.Fields)
                    .Where(e => e.TenantId == tenantId)
                    .ToListAsync(cancellationToken)
                : await db.SemanticEntities.AsNoTracking()
                    .Include(e => e.Fields)
                    .ToListAsync(cancellationToken);
            if (semanticEntities.Count > 0)
                MetadataEnricher.EnrichFromSemanticSchema(columnDetails, nodes, semanticEntities);

            var metadata = new QueryMetadata
            {
                Pattern = pattern,
                Nodes = nodes,
                Relationships = relationships,
                ColumnDetails = columnDetails,
                RowGrain = rowGrain
            };
            var rowsAsStrings = rowResult.Rows
                .Select(row => (IReadOnlyList<string>)row.Select(cell => cell?.ToString() ?? "").ToList())
                .ToList();
            return new GraphQueryResult
            {
                Columns = rowResult.Columns,
                Rows = rowsAsStrings,
                RowCount = rowResult.RowCount,
                Truncated = rowResult.Truncated,
                Metadata = metadata
            };
        }
        catch (ArgumentException ex)
        {
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage(ex.Message)
                .SetCode("CYPHER_VALIDATION")
                .Build());
        }
        catch (ClientException ex)
        {
            logger.LogWarning(ex, "Neo4j client error executing Cypher (rows): {Code} {Message}", ex.Code, ex.Message);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Cypher execution failed: " + ex.Message)
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
        catch (Neo4jException ex)
        {
            logger.LogWarning(ex, "Neo4j error executing Cypher (rows): {Message}", ex.Message);
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Graph database error: " + ex.Message)
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Unexpected error executing Cypher query (rows)");
            throw new GraphQLException(ErrorBuilder.New()
                .SetMessage("Cypher execution failed. See server logs for details.")
                .SetCode("CYPHER_EXECUTION")
                .Build());
        }
    }

    /// <summary>
    /// Return the graph schema (node types, relationship types) for system prompt / agent context.
    /// When workspaceId is set and the workspace has an ontology with Neo4j connection, uses that graph; otherwise default.
    /// workspaceIds reserved for future filtering.
    /// </summary>
    public async Task<GraphSchema> GraphSchemaAsync(
        Guid? workspaceId,
        IReadOnlyList<string>? workspaceIds,
        [Service] INeo4jGraphService graph,
        [Service] IDbContextFactory<AppDbContext> dbFactory,
        [Service] INeo4jGraphServiceFactory neo4jFactory,
        [Service] IHttpContextAccessor accessor,
        CancellationToken cancellationToken)
    {
        _ = workspaceIds; // Reserved for future filtering
        var service = await ResolveGraphServiceAsync(workspaceId, null, dbFactory, neo4jFactory, graph, cancellationToken);

        await using var db = await dbFactory.CreateDbContextAsync(cancellationToken);
        var semanticEntities = await db.SemanticEntities.AsNoTracking().Include(e => e.Fields).ToListAsync(cancellationToken);
            

        var nodeLabels = await service.GetNodeTypesAsync(cancellationToken);
        var nodeTypes = new List<NodeTypeInfo>();
        foreach (var label in nodeLabels)
        {
            var entity = semanticEntities.FirstOrDefault(e => string.Equals(e.NodeLabel, label, StringComparison.OrdinalIgnoreCase));
            string? description = entity?.Description;
            long count = 0;
            try { count = await service.GetNodeCountAsync(label, cancellationToken); } catch { /* ignore */ }
            var propMeta = await service.GetNodePropertyMetadataAsync(label, cancellationToken);
            var properties = new List<SchemaPropertyInfo>();
            if (entity?.Fields != null)
            {
                foreach (var f in entity.Fields.OrderBy(x => x.Name))
                {
                    var dataType = MapDataTypeToGraph(f.DataType);
                    properties.Add(new SchemaPropertyInfo
                    {
                        Name = f.Name,
                        DataType = dataType,
                        Description = f.Description,
                        IsIdentifier = f.Name.Equals("id", StringComparison.OrdinalIgnoreCase),
                        ExampleValues = null,
                        Required = false
                    });
                }
            }
            if (properties.Count == 0)
            {
                foreach (var p in propMeta)
                    properties.Add(new SchemaPropertyInfo
                    {
                        Name = p.Name,
                        DataType = MapDataTypeToGraph(p.DataType),
                        Description = null,
                        IsIdentifier = p.Name.Equals("id", StringComparison.OrdinalIgnoreCase),
                        ExampleValues = null,
                        Required = false
                    });
            }
            nodeTypes.Add(new NodeTypeInfo
            {
                Label = label,
                Description = description,
                Count = count > int.MaxValue ? int.MaxValue : (int)count,
                Properties = properties
            });
        }

        var relTypes = await service.GetEdgeTypesAsync(cancellationToken);
        var relationshipTypes = new List<RelationshipTypeInfo>();
        foreach (var relType in relTypes)
        {
            var (fromLabels, toLabels) = await service.GetRelationshipTypeEndpointsAsync(relType, cancellationToken);
            relationshipTypes.Add(new RelationshipTypeInfo
            {
                Type = relType,
                Description = null,
                FromLabels = fromLabels,
                ToLabels = toLabels,
                Cardinality = Cardinality.ManyToMany,
                Properties = null
            });
        }

        return new GraphSchema
        {
            NodeTypes = nodeTypes,
            RelationshipTypes = relationshipTypes,
            SuggestedPatterns = Array.Empty<SuggestedPattern>()
        };
    }

    private static async Task<INeo4jGraphService> ResolveGraphServiceAsync(
        Guid? workspaceId,
        Guid? ontologyId,
        IDbContextFactory<AppDbContext> dbFactory,
        INeo4jGraphServiceFactory neo4jFactory,
        INeo4jGraphService defaultGraph,
        CancellationToken ct)
    {
        if (workspaceId is { } wid)
        {
            await using var db = await dbFactory.CreateDbContextAsync(ct);
            var workspace = await db.Workspaces.AsNoTracking().FirstOrDefaultAsync(w => w.WorkspaceId == wid, ct);
            if (workspace is null || workspace.OntologyId is null)
                return defaultGraph;
            return await neo4jFactory.GetGraphServiceForOntologyAsync(workspace.OntologyId.Value, ct);
        }
        if (ontologyId is { } oid)
            return await neo4jFactory.GetGraphServiceForOntologyAsync(oid, ct);
        return defaultGraph;
    }

    private static Guid ResolveTenantId(IHttpContextAccessor accessor)
    {
        var http = accessor.HttpContext;
        var tidStr = http?.User?.FindFirst("tid")?.Value ?? http?.Request.Headers["X-Tenant-Id"].ToString();
        if (string.IsNullOrWhiteSpace(tidStr)) return Guid.Empty;
        return Guid.TryParse(tidStr, out var tenantId) ? tenantId : Guid.Empty;
    }

    private static GraphDataType MapDataTypeToGraph(string? dataType)
    {
        if (string.IsNullOrWhiteSpace(dataType)) return GraphDataType.String;
        var d = dataType.Trim();
        if (d.StartsWith("Integer", StringComparison.OrdinalIgnoreCase) || d.Equals("Long", StringComparison.OrdinalIgnoreCase)) return GraphDataType.Integer;
        if (d.StartsWith("Float", StringComparison.OrdinalIgnoreCase) || d.Equals("Double", StringComparison.OrdinalIgnoreCase)) return GraphDataType.Float;
        if (d.StartsWith("Boolean", StringComparison.OrdinalIgnoreCase)) return GraphDataType.Boolean;
        if (d.StartsWith("Date", StringComparison.OrdinalIgnoreCase)) return GraphDataType.Date;
        if (d.StartsWith("List", StringComparison.OrdinalIgnoreCase)) return GraphDataType.List;
        if (d.Equals("Map", StringComparison.OrdinalIgnoreCase)) return GraphDataType.Map;
        return GraphDataType.String;
    }
}
