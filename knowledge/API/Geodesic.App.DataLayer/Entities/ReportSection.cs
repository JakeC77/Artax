namespace Geodesic.App.DataLayer.Entities;

public class ReportSection
{
    public Guid ReportSectionId { get; set; }
    public Guid ReportId { get; set; }
    public Guid? TemplateSectionId { get; set; }
    public string SectionType { get; set; } = default!;
    public string Header { get; set; } = default!;
    public int Order { get; set; }

    public Report? Report { get; set; }
    public ReportTemplateSection? TemplateSection { get; set; }
    public ICollection<ReportBlock> Blocks { get; set; } = new List<ReportBlock>();
}

