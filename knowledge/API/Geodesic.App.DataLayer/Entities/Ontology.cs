namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Tracks ontologies created via the front-end/agent stream. Ontology content lives in external JSON files (see JsonUri).
/// Scoped by tenant; shared across many workspaces within that tenant.
/// </summary>
public class Ontology
{
    public Guid OntologyId { get; set; }
    public Guid TenantId { get; set; }
    public Guid? CompanyId { get; set; }
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public string? SemVer { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public Guid? CreatedBy { get; set; }
    public DateTimeOffset? LastEdit { get; set; }
    public Guid? LastEditedBy { get; set; }
    public string Status { get; set; } = "draft";
    public Guid? RunId { get; set; }
    public string? JsonUri { get; set; }

    /// <summary>Markdown text examples injected into prompts for this ontology's domain.</summary>
    public string? DomainExamples { get; set; }

    /// <summary>When set (with Neo4jUsername and Neo4jEncryptedPassword), this ontology uses its own Neo4j instance (e.g. Aura).</summary>
    public string? Neo4jUri { get; set; }
    public string? Neo4jUsername { get; set; }
    /// <summary>Encrypted password; never exposed via API. Decrypted at runtime using app-level key.</summary>
    public string? Neo4jEncryptedPassword { get; set; }
}
