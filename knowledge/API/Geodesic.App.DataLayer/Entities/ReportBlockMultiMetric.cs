namespace Geodesic.App.DataLayer.Entities;

public class ReportBlockMultiMetric
{
    public Guid ReportBlockId { get; set; }
    public string Metrics { get; set; } = "[]"; // jsonb, array of metric objects

    public ReportBlock? ReportBlock { get; set; }
}

