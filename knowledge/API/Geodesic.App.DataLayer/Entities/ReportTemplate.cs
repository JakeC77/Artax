namespace Geodesic.App.DataLayer.Entities;

public class ReportTemplate
{
    public Guid TemplateId { get; set; }
    public int Version { get; set; }
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }

    public ICollection<ReportTemplateSection> Sections { get; set; } = new List<ReportTemplateSection>();
}

