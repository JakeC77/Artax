namespace Geodesic.App.DataLayer.Entities;

public class ScenarioRunLog
{
    public long LogId { get; set; }
    public Guid TenantId { get; set; }
    public Guid RunId { get; set; }
    public string Content { get; set; } = default!;
    public DateTimeOffset CreatedAt { get; set; }
}

