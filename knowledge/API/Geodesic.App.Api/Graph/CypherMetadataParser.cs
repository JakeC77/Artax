using System.Text.RegularExpressions;

namespace Geodesic.App.Api.Graph;

/// <summary>
/// Heuristic parser for Cypher MATCH and RETURN clauses to extract pattern, nodes, relationships, and column mapping.
/// </summary>
public static class CypherMetadataParser
{
    // (p:Patient) or (p) or (plan:Plan)
    private static readonly Regex NodePattern = new(
        @"\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::([a-zA-Z_][a-zA-Z0-9_]*(?:\s*:\s*[a-zA-Z_][a-zA-Z0-9_]*)*))?\s*\)",
        RegexOptions.Compiled);

    // -[:PATIENT_TO_PLAN]-> or <-[:PATIENT_TO_PLAN]- or -[:TYPE]-
    private static readonly Regex RelPattern = new(
        @"(<-)?\s*\[\s*:?\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\]\s*(->)?",
        RegexOptions.Compiled);

    /// <summary>
    /// Parse MATCH and RETURN from a Cypher query to build metadata.
    /// </summary>
    public static (PatternInfo Pattern, IReadOnlyList<NodeInfo> Nodes, IReadOnlyList<RelationshipInfo> Relationships, IReadOnlyList<ColumnInfo> ColumnDetails, string RowGrain) Parse(
        string cypherQuery,
        IReadOnlyList<string> columnNames)
    {
        var normalized = NormalizeQuery(cypherQuery);
        var matchSection = ExtractMatchSection(normalized);
        var returnSection = ExtractReturnSection(normalized);

        var (pattern, nodes, relationships) = ParseMatch(matchSection);
        var columnDetails = ParseReturnColumns(returnSection, columnNames);
        var rowGrain = InferRowGrain(nodes, relationships, columnDetails, normalized);

        return (pattern, nodes, relationships, columnDetails, rowGrain);
    }

    private static string NormalizeQuery(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return "";
        var s = query.Trim();
        // Remove single-line and multi-line comments
        s = Regex.Replace(s, @"//[^\n]*", "");
        s = Regex.Replace(s, @"/\*.*?\*/", "", RegexOptions.Singleline);
        return s;
    }

    private static string ExtractMatchSection(string query)
    {
        var match = Regex.Match(query, @"\bMATCH\b\s+(.+?)(?=\b(?:WHERE|RETURN|WITH|ORDER|LIMIT|SKIP)\b)", RegexOptions.IgnoreCase | RegexOptions.Singleline);
        return match.Success ? match.Groups[1].Value.Trim() : "";
    }

    private static string ExtractReturnSection(string query)
    {
        var match = Regex.Match(query, @"\bRETURN\b\s+(.+?)(?=\b(?:ORDER|LIMIT|SKIP)\b|$)", RegexOptions.IgnoreCase | RegexOptions.Singleline);
        return match.Success ? match.Groups[1].Value.Trim() : "";
    }

    private static (PatternInfo Pattern, IReadOnlyList<NodeInfo> Nodes, IReadOnlyList<RelationshipInfo> Relationships) ParseMatch(string matchSection)
    {
        var nodes = new List<NodeInfo>();
        var relationships = new List<RelationshipInfo>();
        var nodeAliasToPosition = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        var position = 0;

        // Find all node patterns (alias:Label or alias:Label1:Label2)
        foreach (Match m in NodePattern.Matches(matchSection))
        {
            var alias = m.Groups[1].Value.Trim();
            var labelsStr = m.Groups[2].Success ? m.Groups[2].Value : "";
            var labels = labelsStr
                .Split(':', StringSplitOptions.RemoveEmptyEntries)
                .Select(x => x.Trim())
                .Where(x => x.Length > 0)
                .ToList();
            if (labels.Count == 0 && alias.Length > 0)
                labels.Add(alias);
            if (!nodeAliasToPosition.ContainsKey(alias))
            {
                nodeAliasToPosition[alias] = position++;
                nodes.Add(new NodeInfo { Alias = alias, Labels = labels, PatternPosition = nodeAliasToPosition[alias] });
            }
        }

        // Find relationship patterns: -[:TYPE]-> or <-[:TYPE]- or -[:TYPE]-
        var relMatches = RelPattern.Matches(matchSection);
        var nodeMatches = NodePattern.Matches(matchSection).Cast<Match>().ToList();
        for (var i = 0; i < relMatches.Count; i++)
        {
            var rm = relMatches[i];
            var hasLeftArrow = rm.Groups[1].Success;
            var relType = rm.Groups[2].Value.Trim();
            var hasRightArrow = rm.Groups[3].Success;
            RelationshipDirection direction;
            if (hasLeftArrow && hasRightArrow) direction = RelationshipDirection.Undirected;
            else if (hasRightArrow) direction = RelationshipDirection.Outgoing;
            else if (hasLeftArrow) direction = RelationshipDirection.Incoming;
            else direction = RelationshipDirection.Undirected;

            string fromAlias = "", toAlias = "";
            if (nodeMatches.Count >= i + 2)
            {
                fromAlias = nodeMatches[i].Groups[1].Value.Trim();
                toAlias = nodeMatches[i + 1].Groups[1].Value.Trim();
                if (direction == RelationshipDirection.Incoming)
                    (fromAlias, toAlias) = (toAlias, fromAlias);
            }

            relationships.Add(new RelationshipInfo
            {
                Type = relType,
                FromAlias = fromAlias,
                ToAlias = toAlias,
                Direction = direction
            });
        }

        var cypherPattern = matchSection.Trim();
        var description = BuildPatternDescription(nodes, relationships);
        var pattern = new PatternInfo { Description = description, CypherPattern = cypherPattern };
        return (pattern, nodes, relationships);
    }

    private static string BuildPatternDescription(IReadOnlyList<NodeInfo> nodes, IReadOnlyList<RelationshipInfo> relationships)
    {
        if (nodes.Count == 0) return "Query result";
        if (relationships.Count == 0)
            return nodes.Count == 1
                ? nodes[0].Labels.Count > 0 ? string.Join(" / ", nodes[0].Labels) : "Single node"
                : "Multiple nodes";
        var parts = new List<string>();
        foreach (var n in nodes)
        {
            if (n.Labels.Count > 0)
                parts.Add(string.Join(" / ", n.Labels));
        }
        return parts.Count > 0 ? string.Join(" connected by ", parts) : "Query result";
    }

    private static IReadOnlyList<ColumnInfo> ParseReturnColumns(string returnSection, IReadOnlyList<string> columnNames)
    {
        var result = new List<ColumnInfo>();
        for (var i = 0; i < columnNames.Count; i++)
        {
            var name = columnNames[i];
            string? nodeAlias = null;
            string? property = null;
            var isComputed = name.Contains("(") || name.Contains(" AS ", StringComparison.OrdinalIgnoreCase);

            if (!isComputed && name.Contains('.'))
            {
                var dot = name.IndexOf('.');
                nodeAlias = name[..dot].Trim();
                property = name[(dot + 1)..].Trim();
            }

            var isIdentifier = property?.Equals("id", StringComparison.OrdinalIgnoreCase) ?? false;
            result.Add(new ColumnInfo
            {
                Name = name,
                NodeAlias = nodeAlias,
                Property = property,
                DataType = GraphDataType.String,
                IsIdentifier = isIdentifier,
                Role = isComputed ? ColumnRole.Computed : (isIdentifier ? ColumnRole.Identifier : ColumnRole.Attribute)
            });
        }
        return result;
    }

    private static string InferRowGrain(
        IReadOnlyList<NodeInfo> nodes,
        IReadOnlyList<RelationshipInfo> relationships,
        IReadOnlyList<ColumnInfo> columnDetails,
        string query)
    {
        var hasAggregation = columnDetails.Any(c => c.Role == ColumnRole.Computed) ||
            Regex.IsMatch(query, @"\b(?:count|sum|avg|min|max|collect)\s*\(", RegexOptions.IgnoreCase);
        if (hasAggregation)
            return "One row per aggregation group";
        if (relationships.Count > 0)
            return $"One row per {string.Join("-", relationships.Select(r => r.Type))} match";
        if (nodes.Count == 1 && nodes[0].Labels.Count > 0)
            return $"One row per {string.Join(" / ", nodes[0].Labels)}";
        return "One row per result";
    }
}
