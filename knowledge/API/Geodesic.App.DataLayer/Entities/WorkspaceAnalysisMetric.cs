namespace Geodesic.App.DataLayer.Entities;

public class WorkspaceAnalysisMetric
{
    public Guid WorkspaceAnalysisMetricId { get; set; }
    public Guid WorkspaceAnalysisId { get; set; }
    public string? MainText { get; set; }
    public string? SecondaryText { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
}

