namespace Geodesic.App.DataLayer.Entities;

public class ReportTemplateSection
{
    public Guid TemplateSectionId { get; set; }
    public Guid TemplateId { get; set; }
    public int TemplateVersion { get; set; }
    public string SectionType { get; set; } = default!;
    public string Header { get; set; } = default!;
    public int Order { get; set; }
    public string? SemanticDefinition { get; set; }

    public ReportTemplate? Template { get; set; }
    public ICollection<ReportTemplateBlock> Blocks { get; set; } = new List<ReportTemplateBlock>();
}

