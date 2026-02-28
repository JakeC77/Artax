namespace Geodesic.App.DataLayer.Entities;

public class Report
{
    public Guid ReportId { get; set; }
    public Guid? TemplateId { get; set; }
    public int? TemplateVersion { get; set; }
    public Guid? WorkspaceAnalysisId { get; set; }
    public Guid? ScenarioId { get; set; }
    public string Type { get; set; } = default!; // "analysis" | "scenario"
    public string Title { get; set; } = default!;
    public string Status { get; set; } = default!;
    public string Metadata { get; set; } = "{}"; // jsonb
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }

    public ReportTemplate? Template { get; set; }
    public WorkspaceAnalysis? WorkspaceAnalysis { get; set; }
    public Scenario? Scenario { get; set; }
    public ICollection<ReportSection> Sections { get; set; } = new List<ReportSection>();
    public ICollection<Source> Sources { get; set; } = new List<Source>();
}

