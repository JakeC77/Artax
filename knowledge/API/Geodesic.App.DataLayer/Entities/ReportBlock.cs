namespace Geodesic.App.DataLayer.Entities;

public class ReportBlock
{
    public Guid ReportBlockId { get; set; }
    public Guid ReportSectionId { get; set; }
    public Guid? TemplateBlockId { get; set; }
    public string BlockType { get; set; } = default!;
    public string[] SourceRefs { get; set; } = Array.Empty<string>(); // text[]
    public string Provenance { get; set; } = "{}"; // jsonb
    public string LayoutHints { get; set; } = "{}"; // jsonb
    public int Order { get; set; }

    public ReportSection? ReportSection { get; set; }
    public ReportTemplateBlock? TemplateBlock { get; set; }
}

