using System.Text.Json;
using Geodesic.App.DataLayer;
using Geodesic.App.DataLayer.Entities;
using Geodesic.App.Api.Graph;
using Geodesic.App.Api.Storage;
using Microsoft.EntityFrameworkCore;

namespace Geodesic.App.Api.Services;

public sealed class OntologySemanticSyncService
{
    private static readonly string[] RangeDataTypes = { "date", "integer", "numeric", "float" };

    private readonly IDbContextFactory<AppDbContext> _dbFactory;
    private readonly IFileStorage _storage;
    private readonly INeo4jGraphServiceFactory _neo4jFactory;

    public OntologySemanticSyncService(
        IDbContextFactory<AppDbContext> dbFactory,
        IFileStorage storage,
        INeo4jGraphServiceFactory neo4jFactory)
    {
        _dbFactory = dbFactory;
        _storage = storage;
        _neo4jFactory = neo4jFactory;
    }

    public async Task<SyncOntologyToSemanticEntitiesResult> SyncAsync(Guid ontologyId, CancellationToken ct = default)
    {
        var result = new SyncOntologyToSemanticEntitiesResult();

        await using var db = await _dbFactory.CreateDbContextAsync(ct);

        var ontology = await db.Ontologies
            .AsNoTracking()
            .FirstOrDefaultAsync(x => x.OntologyId == ontologyId, ct);
        if (ontology is null)
            return result;

        string? json = await ResolveOntologyJsonAsync(ontologyId, ontology, ct);
        if (string.IsNullOrWhiteSpace(json))
            return result;

        OntologyDraftRoot? draft;
        try
        {
            draft = JsonSerializer.Deserialize<OntologyDraftRoot>(json);
        }
        catch (JsonException)
        {
            return result;
        }

        if (draft?.Entities is null || draft.Entities.Count == 0)
            return result;

        foreach (var entity in draft.Entities)
        {
            if (string.IsNullOrWhiteSpace(entity.Name))
                continue;

            var existing = await db.SemanticEntities
                .Include(e => e.Fields)
                .FirstOrDefaultAsync(e => e.OntologyId == ontologyId && e.NodeLabel == entity.Name, ct);

            if (existing is null)
            {
                var newEntity = new SemanticEntity
                {
                    SemanticEntityId = Guid.NewGuid(),
                    TenantId = ontology.TenantId,
                    OntologyId = ontologyId,
                    NodeLabel = entity.Name,
                    Name = entity.Name,
                    Description = entity.Description,
                    CreatedOn = DateTimeOffset.UtcNow
                };
                db.SemanticEntities.Add(newEntity);
                await db.SaveChangesAsync(ct);

                foreach (var field in entity.Fields)
                {
                    if (string.IsNullOrWhiteSpace(field.Name))
                        continue;
                    db.SemanticFields.Add(new SemanticField
                    {
                        SemanticFieldId = Guid.NewGuid(),
                        SemanticEntityId = newEntity.SemanticEntityId,
                        Name = field.Name,
                        Description = field.Description,
                        DataType = MapDataType(field.DataType)
                    });
                }
                result.EntitiesCreated++;
            }
            else
            {
                existing.Name = entity.Name;
                existing.Description = entity.Description ?? existing.Description;

                foreach (var field in entity.Fields)
                {
                    if (string.IsNullOrWhiteSpace(field.Name))
                        continue;
                    var existingField = existing.Fields.FirstOrDefault(f => f.Name == field.Name);
                    if (existingField is null)
                    {
                        db.SemanticFields.Add(new SemanticField
                        {
                            SemanticFieldId = Guid.NewGuid(),
                            SemanticEntityId = existing.SemanticEntityId,
                            Name = field.Name,
                            Description = field.Description,
                            DataType = MapDataType(field.DataType)
                        });
                    }
                    else
                    {
                        existingField.Description = field.Description ?? existingField.Description;
                        existingField.DataType = MapDataType(field.DataType) ?? existingField.DataType;
                    }
                }
                result.EntitiesUpdated++;
            }
        }

        await db.SaveChangesAsync(ct);

        var fieldsToRange = await db.SemanticFields
            .Include(f => f.SemanticEntity)
            .Where(f => f.SemanticEntity != null
                && f.SemanticEntity!.OntologyId == ontologyId
                && f.DataType != null
                && RangeDataTypes.Contains(f.DataType))
            .ToListAsync(ct);

        var graph = await _neo4jFactory.GetGraphServiceForOntologyAsync(ontologyId, ct);

        foreach (var field in fieldsToRange)
        {
            if (field.SemanticEntity is null)
                continue;
            try
            {
                var rangeInfo = await CalculateRangeForFieldAsync(graph, field.SemanticEntity.NodeLabel, field.Name, field.DataType!, ct);
                if (field.RangeInfo != rangeInfo)
                {
                    field.RangeInfo = rangeInfo;
                    result.FieldsWithRangeUpdated++;
                }
            }
            catch (Exception)
            {
                // Log and continue
            }
        }

        if (result.FieldsWithRangeUpdated > 0)
            await db.SaveChangesAsync(ct);

        return result;
    }

    private static string? MapDataType(string? dataType)
    {
        if (string.IsNullOrWhiteSpace(dataType))
            return null;
        return dataType == "float" ? "numeric" : dataType;
    }

    private async Task<string?> ResolveOntologyJsonAsync(Guid ontologyId, Ontology ontology, CancellationToken ct)
    {
        string container;
        string blobPath;
        var jsonUri = ontology.JsonUri?.Trim();
        if (!string.IsNullOrEmpty(jsonUri) && Uri.TryCreate(jsonUri, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps) &&
            uri.Host.Contains(".blob.core.windows.net", StringComparison.OrdinalIgnoreCase))
        {
            var pathSegments = uri.AbsolutePath.TrimStart('/').Split('/', StringSplitOptions.RemoveEmptyEntries);
            if (pathSegments.Length < 2)
                return null;
            container = pathSegments[0];
            blobPath = string.Join("/", pathSegments.Skip(1));
        }
        else if (!string.IsNullOrEmpty(jsonUri))
        {
            container = "scratchpad-attachments";
            blobPath = jsonUri;
        }
        else
        {
            container = "scratchpad-attachments";
            blobPath = $"ontology-drafts/{Guid.Empty:D}/{ontologyId}/draft.json";
        }

        return await _storage.GetContentAsStringAsync(container, blobPath, ct);
    }

    private static async Task<string?> CalculateRangeForFieldAsync(
        INeo4jGraphService graph,
        string nodeLabel,
        string fieldName,
        string dataType,
        CancellationToken ct)
    {
        var escapedFieldName = fieldName.Replace("`", "``");
        var escapedNodeLabel = nodeLabel.Replace("`", "``");
        var cypher = $@"
MATCH (n:`{escapedNodeLabel}`)
WHERE n.`{escapedFieldName}` IS NOT NULL
RETURN min(n.`{escapedFieldName}`) as minVal, max(n.`{escapedFieldName}`) as maxVal";

        var result = await graph.ExecuteCypherRowsAsync(cypher, (IReadOnlyList<string>?)null, 1, ct);
        if (result.Rows.Count == 0)
            return null;

        var row = result.Rows[0];
        var minIdx = result.Columns.ToList().IndexOf("minVal");
        var maxIdx = result.Columns.ToList().IndexOf("maxVal");
        object? minVal = minIdx >= 0 && minIdx < row.Count ? row[minIdx] : null;
        object? maxVal = maxIdx >= 0 && maxIdx < row.Count ? row[maxIdx] : null;

        if (minVal == null && maxVal == null)
            return null;

        var rangeObj = new Dictionary<string, string?>();
        if (minVal != null)
            rangeObj["min"] = FormatCellForRange(minVal);
        if (maxVal != null)
            rangeObj["max"] = FormatCellForRange(maxVal);

        return JsonSerializer.Serialize(rangeObj);
    }

    private static string FormatCellForRange(object value)
    {
        return value.ToString() ?? string.Empty;
    }
}
