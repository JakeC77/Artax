namespace Geodesic.App.DataLayer.Entities;

public class SemanticEntity
{
    public Guid SemanticEntityId { get; set; }
    public Guid TenantId { get; set; }
    public Guid? OntologyId { get; set; }
    public string NodeLabel { get; set; } = default!;
    public int Version { get; set; } = 1;
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public DateTimeOffset CreatedOn { get; set; }

    public ICollection<SemanticField> Fields { get; set; } = new List<SemanticField>();
}
