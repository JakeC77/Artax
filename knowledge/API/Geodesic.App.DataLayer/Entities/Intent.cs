namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Tracks intents: actions a third-party agent can perform on behalf of the system.
/// Defines what information the agent must collect, when to execute, and what the response looks like.
/// Tenant-scoped. Optionally linked to one ontology (one ontology has many intents).
/// </summary>
public class Intent
{
    public Guid IntentId { get; set; }
    public Guid TenantId { get; set; }
    /// <summary>When set, this intent belongs to this ontology. One ontology can have many intents.</summary>
    public Guid? OntologyId { get; set; }
    public string OpId { get; set; } = default!;
    public string IntentName { get; set; } = default!;
    public string? Route { get; set; }
    public string? Description { get; set; }
    public string? DataSource { get; set; }
    /// <summary>JSON Schema for input (stored as jsonb).</summary>
    public string? InputSchema { get; set; }
    /// <summary>JSON Schema for output (stored as jsonb).</summary>
    public string? OutputSchema { get; set; }
    /// <summary>Cypher query template for grounding (plain text).</summary>
    public string? Grounding { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public DateTimeOffset? LastEdit { get; set; }
}
