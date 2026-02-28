using System.Text.Json.Serialization;

namespace Geodesic.App.Api.Services;

/// <summary>Root of ontology draft.json (e.g. ANDURIL.json).</summary>
public sealed class OntologyDraftRoot
{
    [JsonPropertyName("entities")]
    public List<OntologyDraftEntity> Entities { get; set; } = new();
}

/// <summary>Entity in ontology draft; name = node label.</summary>
public sealed class OntologyDraftEntity
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = default!;

    [JsonPropertyName("description")]
    public string? Description { get; set; }

    [JsonPropertyName("fields")]
    public List<OntologyDraftField> Fields { get; set; } = new();
}

/// <summary>Field in ontology draft entity.</summary>
public sealed class OntologyDraftField
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = default!;

    [JsonPropertyName("data_type")]
    public string? DataType { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }
}

/// <summary>Result of syncOntologyToSemanticEntities mutation.</summary>
public sealed class SyncOntologyToSemanticEntitiesResult
{
    public int EntitiesCreated { get; set; }
    public int EntitiesUpdated { get; set; }
    public int FieldsWithRangeUpdated { get; set; }
}
