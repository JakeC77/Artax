namespace Geodesic.App.DataLayer.Entities;

public class ReportTemplateBlock
{
    public Guid TemplateBlockId { get; set; }
    public Guid TemplateSectionId { get; set; }
    public string BlockType { get; set; } = default!;
    public int Order { get; set; }
    public string LayoutHints { get; set; } = "{}"; // jsonb
    public string? SemanticDefinition { get; set; }

    public ReportTemplateSection? TemplateSection { get; set; }
}

