namespace Geodesic.App.DataLayer.Entities;

public class ReportBlockInsightCard
{
    public Guid ReportBlockId { get; set; }
    public string Title { get; set; } = default!;
    public string Body { get; set; } = default!;
    public string? Badge { get; set; } // badge text/type
    public string? Severity { get; set; } // e.g., "info", "warning", "critical"

    public ReportBlock? ReportBlock { get; set; }
}

