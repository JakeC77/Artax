namespace Geodesic.App.DataLayer.Entities;

public class ScenarioMetric
{
    public Guid ScenarioMetricId { get; set; }
    public Guid ScenarioId { get; set; }
    public string? MainText { get; set; }
    public string? SecondaryText { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public int Version { get; set; }
}

