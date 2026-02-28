namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Company record; name and markdown content consumed by agentic workflows.
/// Tenant-scoped.
/// </summary>
public class Company
{
    public Guid CompanyId { get; set; }
    public Guid TenantId { get; set; }
    public string Name { get; set; } = default!;
    /// <summary>Markdown document about the company; consumed by agentic workflows.</summary>
    public string? MarkdownContent { get; set; }
}
