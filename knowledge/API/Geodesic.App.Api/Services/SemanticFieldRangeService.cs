using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Microsoft.EntityFrameworkCore;
using Neo4j.Driver;
using System.Text.Json;

namespace Geodesic.App.Api.Services;

public class SemanticFieldRangeService
{
    private readonly IDbContextFactory<AppDbContext> _dbFactory;
    private readonly IDriver _neo4jDriver;
    private readonly string? _neo4jDatabase;

    public SemanticFieldRangeService(
        IDbContextFactory<AppDbContext> dbFactory,
        IDriver neo4jDriver,
        string? neo4jDatabase = null)
    {
        _dbFactory = dbFactory;
        _neo4jDriver = neo4jDriver;
        _neo4jDatabase = neo4jDatabase;
    }

    private IAsyncSession OpenSession()
        => _neo4jDatabase is null
            ? _neo4jDriver.AsyncSession()
            : _neo4jDriver.AsyncSession(o => o.WithDatabase(_neo4jDatabase));

    public async Task<int> CalculateRangesAsync(CancellationToken ct = default)
    {
        await using var db = await _dbFactory.CreateDbContextAsync(ct);

        // Get all semantic fields with numeric/date data types
        var fieldsToProcess = await db.SemanticFields
            .Include(f => f.SemanticEntity)
            .Where(f => f.DataType != null && (
                f.DataType == "date" ||
                f.DataType == "integer" ||
                f.DataType == "numeric" ||
                f.DataType == "timestamp with time zone"))
            .ToListAsync(ct);

        int updatedCount = 0;

        foreach (var field in fieldsToProcess)
        {
            if (field.SemanticEntity == null)
                continue;

            var nodeLabel = field.SemanticEntity.NodeLabel;
            var fieldName = field.Name;

            try
            {
                var rangeInfo = await CalculateRangeForFieldAsync(nodeLabel, fieldName, field.DataType!, ct);
                
                // Always update RangeInfo, even if null (to clear stale data)
                if (field.RangeInfo != rangeInfo)
                {
                    field.RangeInfo = rangeInfo;
                    updatedCount++;
                }
            }
            catch (Exception ex)
            {
                // Log error but continue with other fields
                Console.Error.WriteLine($"Error calculating range for field {fieldName} in {nodeLabel}: {ex.Message}");
            }
        }

        if (updatedCount > 0)
        {
            await db.SaveChangesAsync(ct);
        }

        return updatedCount;
    }

    private async Task<string?> CalculateRangeForFieldAsync(
        string nodeLabel,
        string fieldName,
        string dataType,
        CancellationToken ct)
    {
        await using var session = OpenSession();

        return await session.ExecuteReadAsync<string?>(async tx =>
        {
            // Escape the field name and node label for Cypher
            var escapedFieldName = fieldName.Replace("`", "``");
            var escapedNodeLabel = nodeLabel.Replace("`", "``");

            // Build the Cypher query to get min/max values
            var cypher = $@"
                MATCH (n:`{escapedNodeLabel}`)
                WHERE n.`{escapedFieldName}` IS NOT NULL
                RETURN min(n.`{escapedFieldName}`) as minVal, max(n.`{escapedFieldName}`) as maxVal";

            var cursor = await tx.RunAsync(cypher);
            var records = await cursor.ToListAsync();
            
            if (records.Count == 0)
                return null;
            
            var record = records[0];
            var minVal = record["minVal"];
            var maxVal = record["maxVal"];

            // If both are null, no data exists
            if (minVal == null && maxVal == null)
                return null;

            // Convert values to appropriate string format based on data type
            string? minStr = null;
            string? maxStr = null;

            if (minVal != null)
            {
                minStr = FormatValueForRange(minVal, dataType);
            }

            if (maxVal != null)
            {
                maxStr = FormatValueForRange(maxVal, dataType);
            }

            // Create JSON object
            var rangeObj = new Dictionary<string, string?>();
            if (minStr != null)
                rangeObj["min"] = minStr;
            if (maxStr != null)
                rangeObj["max"] = maxStr;

            return JsonSerializer.Serialize(rangeObj);
        });
    }

    private string FormatValueForRange(object value, string dataType)
    {
        // Handle Neo4j date types (these are in Neo4j.Driver namespace, not Types)
        if (value is LocalDate localDate)
        {
            return localDate.ToString(); // Returns ISO format: YYYY-MM-DD
        }
        
        if (value is ZonedDateTime zonedDateTime)
        {
            return zonedDateTime.ToDateTimeOffset().ToString("O"); // ISO 8601 with timezone
        }
        
        if (value is LocalDateTime localDateTime)
        {
            return localDateTime.ToDateTime().ToString("yyyy-MM-ddTHH:mm:ss");
        }
        
        // Handle .NET date types
        if (value is DateTime date)
        {
            return dataType == "date" ? date.ToString("yyyy-MM-dd") : date.ToString("O");
        }
        
        if (value is DateTimeOffset dto)
        {
            return dto.ToString("O");
        }
        
        // For numeric and integer types, return as string
        return value.ToString()!;
    }
}

