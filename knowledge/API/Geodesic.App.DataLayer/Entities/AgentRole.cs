namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Profile for what incoming agents are allowed to do: read/write ontology scope and allowed intents.
/// Tenant-scoped.
/// </summary>
public class AgentRole
{
    public Guid AgentRoleId { get; set; }
    public Guid TenantId { get; set; }
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    /// <summary>Ontology the agent can read from. Optional.</summary>
    public Guid? ReadOntologyId { get; set; }
    /// <summary>Ontology the agent can write to. Optional.</summary>
    public Guid? WriteOntologyId { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public DateTimeOffset? LastEdit { get; set; }
}
