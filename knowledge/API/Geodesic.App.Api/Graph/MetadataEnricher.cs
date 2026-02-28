using System.Collections;
using Geodesic.App.DataLayer.Entities;

namespace Geodesic.App.Api.Graph;

/// <summary>
/// Enriches column metadata (dataType, description, role) from first row values and SemanticEntity/SemanticField.
/// </summary>
public static class MetadataEnricher
{
    /// <summary>
    /// Enrich column details with data types inferred from the first row of data.
    /// </summary>
    public static void EnrichFromFirstRow(IReadOnlyList<ColumnInfo> columnDetails, IReadOnlyList<object?> firstRow)
    {
        if (firstRow.Count == 0) return;
        for (var i = 0; i < columnDetails.Count && i < firstRow.Count; i++)
        {
            var col = columnDetails[i];
            var value = firstRow[i];
            col.DataType = InferDataType(value);
            if (col.Role == ColumnRole.Attribute && (col.DataType == GraphDataType.Float || col.DataType == GraphDataType.Integer))
                col.Role = ColumnRole.Metric;
        }
    }

    /// <summary>
    /// Enrich column details from SemanticEntity/SemanticField: dataType, description, isIdentifier.
    /// Maps (nodeAlias → label from nodes) then (NodeLabel, property Name) → SemanticEntity + SemanticField.
    /// </summary>
    public static void EnrichFromSemanticSchema(
        IReadOnlyList<ColumnInfo> columnDetails,
        IReadOnlyList<NodeInfo> nodes,
        IReadOnlyList<SemanticEntity> semanticEntities)
    {
        if (semanticEntities.Count == 0) return;
        var entityByLabel = semanticEntities.ToDictionary(e => e.NodeLabel, StringComparer.OrdinalIgnoreCase);
        var aliasToLabels = nodes.ToDictionary(n => n.Alias, n => n.Labels, StringComparer.OrdinalIgnoreCase);

        foreach (var col in columnDetails)
        {
            if (string.IsNullOrWhiteSpace(col.NodeAlias) || string.IsNullOrWhiteSpace(col.Property)) continue;
            if (!aliasToLabels.TryGetValue(col.NodeAlias, out var labels) || labels.Count == 0) continue;

            foreach (var label in labels)
            {
                if (!entityByLabel.TryGetValue(label, out var entity) || entity.Fields == null) continue;
                var field = entity.Fields.FirstOrDefault(f => string.Equals(f.Name, col.Property, StringComparison.OrdinalIgnoreCase));
                if (field == null) continue;

                col.DataType = MapDataTypeToGraph(field.DataType);
                col.Description = field.Description;
                col.IsIdentifier = field.Name.Equals("id", StringComparison.OrdinalIgnoreCase);
                break;
            }
        }
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

    private static GraphDataType InferDataType(object? value)
    {
        if (value is null) return GraphDataType.Null;
        if (value is string) return GraphDataType.String;
        if (value is bool) return GraphDataType.Boolean;
        if (value is long or int or short or byte) return GraphDataType.Integer;
        if (value is double or float or decimal) return GraphDataType.Float;
        if (value is DateTime or DateOnly) return GraphDataType.Date;
        if (value is IList) return GraphDataType.List;
        if (value is IDictionary) return GraphDataType.Map;
        return GraphDataType.String;
    }
}
