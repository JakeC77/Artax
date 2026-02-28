using System.Collections;
using Microsoft.Extensions.Logging;
using Neo4j.Driver;

namespace Geodesic.App.Api.Graph;

public sealed class Neo4jGraphService : INeo4jGraphService
{
    private const int CypherLogMaxLength = 2000;

    private readonly IDriver _driver;
    private readonly string? _database;
    private readonly ILogger<Neo4jGraphService>? _logger;

    public Neo4jGraphService(IDriver driver, string? database, ILogger<Neo4jGraphService>? logger = null)
    {
        _driver = driver;
        _database = string.IsNullOrWhiteSpace(database) ? null : database;
        _logger = logger;
    }

    private IAsyncSession OpenSession()
        => _database is null
            ? _driver.AsyncSession()
            : _driver.AsyncSession(o => o.WithDatabase(_database));

    public async Task<GraphNode?> GetNodeByIdAsync(string id, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<GraphNode?>(async tx =>
        {
            var cursor = await tx.RunAsync(
                "MATCH (n {id: $id}) RETURN n as n, labels(n) as labels",
                new { id });
            var list = await cursor.ToListAsync();
            var rec = list.FirstOrDefault();
            if (rec is null) return (GraphNode?)null;
            var node = rec["n"].As<Neo4j.Driver.INode>();
            var labels = rec["labels"].As<List<string>>();
            return new GraphNode
            {
                Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : id,
                Labels = labels,
                Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
            };
        });
    }

    public async Task<GraphEdge?> GetEdgeByIdAsync(string id, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<GraphEdge?>(async tx =>
        {
            var cursor = await tx.RunAsync(
                "MATCH (a)-[r]-(b) WHERE r.id = $id OR elementId(r) = $id RETURN r as r, type(r) as type, a.id as fromId, b.id as toId",
                new { id });
            var list = await cursor.ToListAsync();
            var rec = list.FirstOrDefault();
            if (rec is null) return (GraphEdge?)null;
            var rel = rec["r"].As<IRelationship>();
            return new GraphEdge
            {
                Id = rel.Properties.ContainsKey("id")
                    ? rel.Properties["id"]?.ToString() ?? string.Empty
                    : (rel.ElementId ?? id),
                Type = rec["type"].As<string>(),
                FromId = rec["fromId"].As<string>(),
                ToId = rec["toId"].As<string>(),
                Properties = rel.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
            };
        });
    }

    public async Task<GraphNode> UpsertNodeAsync(string id, string type, IReadOnlyDictionary<string, string>? properties, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteWriteAsync<GraphNode>(async tx =>
        {
            // Use parameterized label via string interpolation for label only
            var cypher = $"MERGE (n:`{type}` {{id: $id}}) SET n += $props RETURN n as n, labels(n) as labels";
            var cursor = await tx.RunAsync(cypher, new
            {
                id,
                props = (object)(properties ?? new Dictionary<string, string>())
            });
            var rec = await cursor.SingleAsync();
            var node = rec["n"].As<Neo4j.Driver.INode>();
            var labels = rec["labels"].As<List<string>>();
            return new GraphNode
            {
                Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : id,
                Labels = labels,
                Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
            };
        });
    }

    public async Task<GraphEdge> UpsertEdgeAsync(string id, string type, string fromId, string toId, IReadOnlyDictionary<string, string>? properties, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteWriteAsync<GraphEdge>(async tx =>
        {
            var cypher = $@"
                MERGE (a {{id: $fromId}})
                MERGE (b {{id: $toId}})
                MERGE (a)-[r:`{type}` {{id: $id}}]->(b)
                SET r += $props
                RETURN r as r, type(r) as type, a.id as fromId, b.id as toId
            ";
            var cursor = await tx.RunAsync(cypher, new
            {
                id,
                fromId,
                toId,
                props = (object)(properties ?? new Dictionary<string, string>())
            });
            var rec = await cursor.SingleAsync();
            var rel = rec["r"].As<IRelationship>();
            return new GraphEdge
            {
                Id = rel.Properties.ContainsKey("id")
                    ? rel.Properties["id"]?.ToString() ?? string.Empty
                    : (rel.ElementId ?? id),
                Type = rec["type"].As<string>(),
                FromId = rec["fromId"].As<string>(),
                ToId = rec["toId"].As<string>(),
                Properties = rel.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
            };
        });
    }

    public async Task<IReadOnlyList<string>> GetNodeTypesAsync(CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<IReadOnlyList<string>>(async tx =>
        {
            var cursor = await tx.RunAsync(
                "MATCH (n) UNWIND labels(n) as label RETURN DISTINCT label ORDER BY label");
            var list = new List<string>();
            await cursor.ForEachAsync(r => list.Add(r["label"].As<string>()));
            return (IReadOnlyList<string>)list;
        });
    }

    public async Task<IReadOnlyList<string>> GetEdgeTypesAsync(CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<IReadOnlyList<string>>(async tx =>
        {
            var cursor = await tx.RunAsync(
                "MATCH ()-[r]-() RETURN DISTINCT type(r) as type ORDER BY type");
            var list = new List<string>();
            await cursor.ForEachAsync(r => list.Add(r["type"].As<string>()));
            return (IReadOnlyList<string>)list;
        });
    }

    public async Task<IReadOnlyList<GraphNode>> GetNodesByTypeAsync(string type, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<IReadOnlyList<GraphNode>>(async tx =>
        {
            var cypher = $"MATCH (n:`{type}`) RETURN n as n, labels(n) as labels";
            var cursor = await tx.RunAsync(cypher);
            var results = new List<GraphNode>();
            await cursor.ForEachAsync(rec =>
            {
                var node = rec["n"].As<Neo4j.Driver.INode>();
                var labels = rec["labels"].As<List<string>>();
                results.Add(new GraphNode
                {
                    Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                    Labels = labels,
                    Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                });
            });
            return (IReadOnlyList<GraphNode>)results;
        });
    }

    public async Task<GraphNeighborhood> GetNeighborsAsync(string id, CancellationToken ct = default)
    {
        await using var session = OpenSession();

        return await session.ExecuteReadAsync<GraphNeighborhood>(async tx =>
        {
            // Fetch neighbor nodes
            var nodeCursor = await tx.RunAsync(
                "MATCH (n {id: $id})--(m) RETURN DISTINCT m as n, labels(m) as labels",
                new { id });
            var nodes = new List<GraphNode>();
            await nodeCursor.ForEachAsync(rec =>
            {
                var node = rec["n"].As<Neo4j.Driver.INode>();
                var labels = rec["labels"].As<List<string>>();
                nodes.Add(new GraphNode
                {
                    Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                    Labels = labels,
                    Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                });
            });

            // Fetch connecting edges (both directions)
            var edgeCursor = await tx.RunAsync(
                "MATCH (a {id: $id})-[r]-(b) RETURN DISTINCT r as r, type(r) as type, a.id as fromId, b.id as toId",
                new { id });
            var edges = new List<GraphEdge>();
            await edgeCursor.ForEachAsync(rec =>
            {
                var rel = rec["r"].As<IRelationship>();
                edges.Add(new GraphEdge
                {
                    Id = rel.Properties.ContainsKey("id")
                        ? rel.Properties["id"]?.ToString() ?? string.Empty
                        : (rel.ElementId ?? string.Empty),
                    Type = rec["type"].As<string>(),
                    FromId = rec["fromId"].As<string>(),
                    ToId = rec["toId"].As<string>(),
                    Properties = rel.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                });
            });

            return new GraphNeighborhood
            {
                Nodes = nodes,
                Edges = edges
            };
        });
    }

    public async Task<IReadOnlyList<GraphNode>> SearchNodesAsync(
        IReadOnlyList<GraphPropertyMatch> criteria,
        string? type = null,
        CancellationToken ct = default)
    {
        await using var session = OpenSession();

        if (criteria is null || criteria.Count == 0)
        {
            return Array.Empty<GraphNode>();
        }

        var paramObject = new Dictionary<string, object?>();
        var labelClause = string.IsNullOrWhiteSpace(type) ? "" : $":`{type}`";

        // Build an APOC-based Levenshtein query first; fall back if APOC not available
        string BuildQuery(bool useApoc)
        {
            var wherePartsInner = new List<string>();
            paramObject.Clear();
            for (int i = 0; i < criteria.Count; i++)
            {
                var c = criteria[i];
                var pName = $"p{i}";
                var dName = $"d{i}";
                paramObject[pName] = c.Value;
                var escapedProp = c.Property.Replace("`", "``");

                if (c.FuzzySearch)
                {
                    if (useApoc)
                    {
                        paramObject[dName] = (object?)(c.MaxDistance ?? 2);
                        wherePartsInner.Add($"n.`{escapedProp}` IS NOT NULL AND apoc.text.levenshteinDistance(toLower(toString(n.`{escapedProp}`)), toLower(${pName})) <= ${dName}");
                    }
                    else
                    {
                        // Fallback: case-insensitive substring if APOC missing
                        wherePartsInner.Add($"n.`{escapedProp}` IS NOT NULL AND toLower(toString(n.`{escapedProp}`)) CONTAINS toLower(${pName})");
                    }
                }
                else
                {
                    wherePartsInner.Add($"n.`{escapedProp}` = ${pName}");
                }
            }
            var whereClauseInner = string.Join(" AND ", wherePartsInner);
            return $"MATCH (n{labelClause}) WHERE {whereClauseInner} RETURN n as n, labels(n) as labels";
        }

        return await session.ExecuteReadAsync<IReadOnlyList<GraphNode>>(async tx =>
        {
            var results = new List<GraphNode>();
            try
            {
                var cypherApoc = BuildQuery(useApoc: true);
                var cursor = await tx.RunAsync(cypherApoc, paramObject);
                await cursor.ForEachAsync(rec =>
                {
                    var node = rec["n"].As<Neo4j.Driver.INode>();
                    var labels = rec["labels"].As<List<string>>();
                    results.Add(new GraphNode
                    {
                        Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                        Labels = labels,
                        Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                    });
                });
            }
            catch (Neo4jException)
            {
                // Fallback to CONTAINS-based fuzzy if APOC text function is unavailable
                var cypherFallback = BuildQuery(useApoc: false);
                var cursor = await tx.RunAsync(cypherFallback, paramObject);
                await cursor.ForEachAsync(rec =>
                {
                    var node = rec["n"].As<Neo4j.Driver.INode>();
                    var labels = rec["labels"].As<List<string>>();
                    results.Add(new GraphNode
                    {
                        Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                        Labels = labels,
                        Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                    });
                });
            }

            return (IReadOnlyList<GraphNode>)results;
        });
    }

    public async Task<IReadOnlyList<GraphNode>> SearchNodesWithFiltersAsync(
        GraphFilterGroup filterGroup,
        string? type = null,
        CancellationToken ct = default)
    {
        await using var session = OpenSession();

        if (filterGroup is null)
        {
            return Array.Empty<GraphNode>();
        }

        var paramObject = new Dictionary<string, object?>();
        var paramCounter = 0;
        var labelClause = string.IsNullOrWhiteSpace(type) ? "" : $":`{type}`";

        // Recursively build WHERE clause from filter groups
        // Structure: A group can have both Filters (direct conditions) and Groups (nested logic)
        // All items (filters + groups) are combined using the group's Operator (AND/OR)
        // Nested groups are wrapped in parentheses to preserve their internal logic
        string BuildWhereClause(GraphFilterGroup group, bool useApoc)
        {
            var parts = new List<string>();

            // Process direct filter conditions (leaf nodes)
            if (group.Filters is not null && group.Filters.Count > 0)
            {
                foreach (var filter in group.Filters)
                {
                    var clause = BuildFilterClause(filter, ref paramCounter, useApoc);
                    if (!string.IsNullOrEmpty(clause))
                    {
                        parts.Add(clause);
                    }
                }
            }

            // Process nested groups (each wrapped in parentheses)
            if (group.Groups is not null && group.Groups.Count > 0)
            {
                foreach (var nestedGroup in group.Groups)
                {
                    var nestedClause = BuildWhereClause(nestedGroup, useApoc);
                    if (!string.IsNullOrEmpty(nestedClause))
                    {
                        // Wrap nested groups in parentheses to preserve their internal logic
                        parts.Add($"({nestedClause})");
                    }
                }
            }

            if (parts.Count == 0)
            {
                return string.Empty;
            }

            // Combine all parts (both filters and nested groups) using the group's operator
            var operatorStr = group.Operator?.ToUpperInvariant() == "OR" ? " OR " : " AND ";
            return string.Join(operatorStr, parts);
        }

        string BuildFilterClause(GraphPropertyMatch filter, ref int paramIndex, bool useApoc)
        {
            var escapedProp = filter.Property.Replace("`", "``");
            var pName = $"p{paramIndex}";
            paramIndex++;

            // Determine operator (default to "eq" if not specified)
            var op = filter.Operator?.ToLowerInvariant() ?? "eq";

            // Handle fuzzy search for strings (takes precedence over operator)
            if (filter.FuzzySearch)
            {
                var dName = $"d{paramIndex}";
                paramIndex++;
                paramObject[dName] = (object?)(filter.MaxDistance ?? 2);
                paramObject[pName] = filter.Value;

                if (useApoc)
                {
                    return $"n.`{escapedProp}` IS NOT NULL AND apoc.text.levenshteinDistance(toLower(toString(n.`{escapedProp}`)), toLower(${pName})) <= ${dName}";
                }
                else
                {
                    return $"n.`{escapedProp}` IS NOT NULL AND toLower(toString(n.`{escapedProp}`)) CONTAINS toLower(${pName})";
                }
            }

            // Handle comparison operators
            paramObject[pName] = filter.Value;
            var propertyRef = $"n.`{escapedProp}`";

            return op switch
            {
                "eq" or "on" => $"{propertyRef} = ${pName}",
                "gt" or "after" => $"{propertyRef} > ${pName}",
                "lt" or "before" => $"{propertyRef} < ${pName}",
                _ => $"{propertyRef} = ${pName}" // Default to equality
            };
        }

        string BuildQuery(bool useApoc)
        {
            paramObject.Clear();
            paramCounter = 0;
            var whereClause = BuildWhereClause(filterGroup, useApoc);

            if (string.IsNullOrEmpty(whereClause))
            {
                return $"MATCH (n{labelClause}) RETURN n as n, labels(n) as labels";
            }

            return $"MATCH (n{labelClause}) WHERE {whereClause} RETURN n as n, labels(n) as labels";
        }

        return await session.ExecuteReadAsync<IReadOnlyList<GraphNode>>(async tx =>
        {
            var results = new List<GraphNode>();
            try
            {
                var cypherApoc = BuildQuery(useApoc: true);
                var cursor = await tx.RunAsync(cypherApoc, paramObject);
                await cursor.ForEachAsync(rec =>
                {
                    var node = rec["n"].As<Neo4j.Driver.INode>();
                    var labels = rec["labels"].As<List<string>>();
                    results.Add(new GraphNode
                    {
                        Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                        Labels = labels,
                        Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                    });
                });
            }
            catch (Neo4jException)
            {
                // Fallback to CONTAINS-based fuzzy if APOC text function is unavailable
                var cypherFallback = BuildQuery(useApoc: false);
                var cursor = await tx.RunAsync(cypherFallback, paramObject);
                await cursor.ForEachAsync(rec =>
                {
                    var node = rec["n"].As<Neo4j.Driver.INode>();
                    var labels = rec["labels"].As<List<string>>();
                    results.Add(new GraphNode
                    {
                        Id = node.Properties.ContainsKey("id") ? node.Properties["id"]?.ToString() ?? string.Empty : string.Empty,
                        Labels = labels,
                        Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                    });
                });
            }

            return (IReadOnlyList<GraphNode>)results;
        });
    }

    public async Task<IReadOnlyList<GraphPropertyMetadata>> GetNodePropertyMetadataAsync(string type, CancellationToken ct = default)
    {
        await using var session = OpenSession();

        return await session.ExecuteReadAsync<IReadOnlyList<GraphPropertyMetadata>>(async tx =>
        {
            var metadata = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
            try
            {
                var cypher = @"
                    CALL db.schema.nodeTypeProperties()
                    YIELD nodeLabels, propertyName, propertyTypes
                    WHERE $label IN nodeLabels
                    RETURN propertyName as name, propertyTypes as types";
                var cursor = await tx.RunAsync(cypher, new { label = type });
                await cursor.ForEachAsync(rec =>
                {
                    var name = rec["name"].As<string>();
                    var types = rec["types"].As<List<string>>() ?? new List<string>();
                    if (!metadata.TryGetValue(name, out var set))
                    {
                        set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                        metadata[name] = set;
                    }

                    if (types.Count == 0)
                    {
                        set.Add("Unknown");
                    }
                    else
                    {
                        foreach (var t in types)
                        {
                            set.Add(string.IsNullOrWhiteSpace(t) ? "Unknown" : t);
                        }
                    }
                });

                if (metadata.Count > 0)
                {
                    return ConvertPropertyMetadata(metadata);
                }
            }
            catch (ClientException)
            {
                metadata.Clear();
            }
            catch (Neo4jException)
            {
                metadata.Clear();
            }

            var fallbackMetadata = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
            var fallbackCypher = $"MATCH (n:`{type}`) UNWIND keys(n) as prop RETURN prop as name, n[prop] as value";
            var fallbackCursor = await tx.RunAsync(fallbackCypher);
            await fallbackCursor.ForEachAsync(rec =>
            {
                var name = rec["name"].As<string>();
                var value = rec["value"];
                if (!fallbackMetadata.TryGetValue(name, out var set))
                {
                    set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                    fallbackMetadata[name] = set;
                }

                set.Add(InferNeo4jPropertyType(value));
            });

            return ConvertPropertyMetadata(fallbackMetadata);
        });
    }

    public async Task<IReadOnlyList<string>> GetNodeRelationshipTypesAsync(string type, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync<IReadOnlyList<string>>(async tx =>
        {
            var cypher = $"MATCH (n:`{type}`)-[r]-() RETURN DISTINCT type(r) as rel ORDER BY rel";
            var cursor = await tx.RunAsync(cypher);
            var relations = new List<string>();
            await cursor.ForEachAsync(rec =>
            {
                var rel = rec["rel"].As<string?>();
                if (!string.IsNullOrWhiteSpace(rel))
                {
                    relations.Add(rel);
                }
            });

            return (IReadOnlyList<string>)relations;
        });
    }

    public async Task<long> GetNodeCountAsync(string label, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync(async tx =>
        {
            var cypher = $"MATCH (n:`{label}`) RETURN count(n) as c";
            var cursor = await tx.RunAsync(cypher);
            var rec = await cursor.SingleAsync();
            return rec["c"].As<long>();
        });
    }

    public async Task<(IReadOnlyList<string> FromLabels, IReadOnlyList<string> ToLabels)> GetRelationshipTypeEndpointsAsync(string relationshipType, CancellationToken ct = default)
    {
        await using var session = OpenSession();
        return await session.ExecuteReadAsync(async tx =>
        {
            var fromSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var toSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var cypher = $"MATCH (a)-[r:`{relationshipType}`]->(b) RETURN DISTINCT labels(a) as fromLabels, labels(b) as toLabels";
            try
            {
                var cursor = await tx.RunAsync(cypher);
                await cursor.ForEachAsync(rec =>
                {
                    var fromLabels = rec["fromLabels"].As<List<string>>() ?? new List<string>();
                    var toLabels = rec["toLabels"].As<List<string>>() ?? new List<string>();
                    foreach (var l in fromLabels) fromSet.Add(l);
                    foreach (var l in toLabels) toSet.Add(l);
                });
            }
            catch (ClientException)
            {
                // Relationship type may not exist or syntax may vary
            }
            return ((IReadOnlyList<string>)fromSet.ToList(), (IReadOnlyList<string>)toSet.ToList());
        });
    }

    private static IReadOnlyList<GraphPropertyMetadata> ConvertPropertyMetadata(Dictionary<string, HashSet<string>> metadata)
    {
        var results = metadata
            .OrderBy(kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
            .Select(kvp =>
            {
                var types = kvp.Value.Count == 0
                    ? new[] { "Unknown" }
                    : kvp.Value.OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToArray();
                return new GraphPropertyMetadata
                {
                    Name = kvp.Key,
                    DataType = types.Length == 1 ? types[0] : string.Join(" | ", types)
                };
            })
            .ToList();

        return results;
    }

    private static string InferNeo4jPropertyType(object? value)
        => value switch
        {
            null => "Unknown",
            string => "String",
            bool => "Boolean",
            sbyte or byte or short or ushort or int or uint or long or ulong => "Integer",
            float or double or decimal => "Float",
            byte[] => "ByteArray",
            IList list => DescribeListType(list),
            IDictionary => "Map",
            LocalDateTime => "LocalDateTime",
            ZonedDateTime => "ZonedDateTime",
            LocalDate => "LocalDate",
            LocalTime => "LocalTime",
            OffsetTime => "OffsetTime",
            Duration => "Duration",
            Point => "Point",
            DateTime => "DateTime",
            _ => value.GetType().Name
        };

    private static string DescribeListType(IList list)
    {
        if (list.Count == 0)
        {
            return "List<Unknown>";
        }

        foreach (var entry in list)
        {
            if (entry is not null)
            {
                return $"List<{InferNeo4jPropertyType(entry)}>";
            }
        }

        return "List<Unknown>";
    }

    public async Task<IReadOnlyList<GraphNode>> ExecuteCypherQueryAsync(string cypherQuery, CancellationToken ct = default)
    {
        // Validate that the query is read-only
        CypherQueryValidator.ValidateReadOnly(cypherQuery);

        var logQuery = cypherQuery.Length > CypherLogMaxLength ? cypherQuery[..CypherLogMaxLength] + "..." : cypherQuery;
        _logger?.LogInformation("Executing Cypher (graphNodesByCypher): {CypherQuery}", logQuery);

        await using var session = OpenSession();
        return await session.ExecuteReadAsync<IReadOnlyList<GraphNode>>(async tx =>
        {
            var cursor = await tx.RunAsync(cypherQuery);
            var results = new List<GraphNode>();
            
            await cursor.ForEachAsync(rec =>
            {
                // Extract nodes from the record
                // A record can contain multiple values, and nodes might be returned in various formats
                foreach (var key in rec.Keys)
                {
                    var value = rec[key];
                    
                    // Check if the value is a node
                    if (value is Neo4j.Driver.INode node)
                    {
                        var labels = node.Labels.ToList();
                        results.Add(new GraphNode
                        {
                            Id = node.Properties.ContainsKey("id")
                                ? node.Properties["id"]?.ToString() ?? string.Empty
                                : (node.ElementId ?? string.Empty),
                            Labels = labels,
                            Properties = node.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                        });
                    }
                    // Also check if the value is a list that might contain nodes
                    else if (value is System.Collections.IList list)
                    {
                        foreach (var item in list)
                        {
                            if (item is Neo4j.Driver.INode listNode)
                            {
                                var labels = listNode.Labels.ToList();
                                results.Add(new GraphNode
                                {
                                    Id = listNode.Properties.ContainsKey("id")
                                        ? listNode.Properties["id"]?.ToString() ?? string.Empty
                                        : (listNode.ElementId ?? string.Empty),
                                    Labels = labels,
                                    Properties = listNode.Properties.ToDictionary(k => k.Key, v => v.Value?.ToString() ?? string.Empty)
                                });
                            }
                        }
                    }
                }
            });

            // Remove duplicates based on node ID (if available)
            var uniqueResults = results
                .GroupBy(n => n.Id)
                .Select(g => g.First())
                .ToList();

            return (IReadOnlyList<GraphNode>)uniqueResults;
        });
    }

    public Task<CypherRowResult> ExecuteCypherRowsAsync(
        string cypherQuery,
        IReadOnlyList<string>? workspaceIds,
        int limit,
        CancellationToken ct = default)
    {
        return ExecuteCypherRowsAsync(cypherQuery, parameters: null, limit, ct);
    }

    public async Task<CypherRowResult> ExecuteCypherRowsAsync(
        string cypherQuery,
        IReadOnlyDictionary<string, object?>? parameters,
        int limit,
        CancellationToken ct = default)
    {
        CypherQueryValidator.ValidateReadOnly(cypherQuery);

        var logQuery = cypherQuery.Length > CypherLogMaxLength ? cypherQuery[..CypherLogMaxLength] + "..." : cypherQuery;
        _logger?.LogInformation("Executing Cypher (with parameters): {CypherQuery}", logQuery);

        await using var session = OpenSession();
        return await session.ExecuteReadAsync(async tx =>
        {
            IResultCursor cursor;
            if (parameters != null && parameters.Count > 0)
            {
                var paramDict = new Dictionary<string, object?>(parameters);
                cursor = await tx.RunAsync(cypherQuery, paramDict);
            }
            else
            {
                cursor = await tx.RunAsync(cypherQuery);
            }

            var records = await cursor.ToListAsync();
            IReadOnlyList<string> columns = Array.Empty<string>();
            var rows = new List<IReadOnlyList<object?>>(Math.Min(records.Count, limit));

            for (var i = 0; i < records.Count && rows.Count < limit; i++)
            {
                var rec = records[i];
                if (i == 0)
                    columns = rec.Keys.ToList();

                var row = new List<object?>(columns.Count);
                foreach (var key in columns)
                {
                    object? value = null;
                    try { value = rec[key]; } catch { /* key missing in record */ }
                    row.Add(ToCellValue(value));
                }
                rows.Add(row);
            }

            var truncated = records.Count > limit;
            return new CypherRowResult
            {
                Columns = columns,
                Rows = rows,
                RowCount = rows.Count,
                Truncated = truncated
            };
        });
    }

    /// <summary>
    /// Converts a Neo4j driver value to a JSON-serializable cell value (string, number, boolean, null).
    /// Complex types (node, relationship, list, map, date) are serialized to string.
    /// </summary>
    private static object? ToCellValue(object? value)
    {
        if (value is null)
            return null;
        if (value is string s)
            return s;
        if (value is bool b)
            return b;
        if (value is long or int or short or byte or sbyte or ushort or uint or ulong)
            return Convert.ToInt64(value);
        if (value is double or float or decimal)
            return Convert.ToDouble(value);
        // Neo4j temporal types: convert to ISO string
        if (value is LocalDate ld)
            return ld.ToString();
        if (value is LocalTime lt)
            return lt.ToString();
        if (value is LocalDateTime ldt)
            return ldt.ToString();
        if (value is ZonedDateTime zdt)
            return zdt.ToString();
        if (value is Duration d)
            return d.ToString();
        // Node: return id if available, else JSON-like string
        if (value is Neo4j.Driver.INode node)
        {
            if (node.Properties.TryGetValue("id", out var idVal))
                return idVal?.ToString();
            return node.ElementId ?? node.Labels.FirstOrDefault() ?? "Node";
        }
        // Relationship: return type or id
        if (value is Neo4j.Driver.IRelationship rel)
            return rel.Type ?? rel.ElementId ?? "Relationship";
        // List/Dictionary: serialize to string for display
        if (value is IList list)
        {
            var items = new List<object?>();
            foreach (var item in list)
                items.Add(ToCellValue(item));
            return System.Text.Json.JsonSerializer.Serialize(items);
        }
        if (value is IDictionary dict)
        {
            var obj = new Dictionary<string, object?>();
            foreach (DictionaryEntry entry in dict)
                obj[entry.Key?.ToString() ?? ""] = ToCellValue(entry.Value);
            return System.Text.Json.JsonSerializer.Serialize(obj);
        }
        return value.ToString();
    }
}
