namespace Geodesic.App.DataLayer.Entities;

public class ReportBlockSingleMetric
{
    public Guid ReportBlockId { get; set; }
    public string Label { get; set; } = default!;
    public string Value { get; set; } = default!;
    public string? Unit { get; set; }
    public string? Trend { get; set; } // e.g., "up", "down", "stable"

    public ReportBlock? ReportBlock { get; set; }
}

