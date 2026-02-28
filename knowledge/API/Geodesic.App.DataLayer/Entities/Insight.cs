
namespace Geodesic.App.DataLayer.Entities;
public class Insight
{
    public Guid InsightId { get; set; }
    public Guid TenantId { get; set; }
    public Guid? WorkspaceId { get; set; }
    public string Severity { get; set; } = "info"; // info|warning|critical
    public string Title { get; set; } = default!;
    public string Body { get; set; } = default!;
    public string[] RelatedGraphIds { get; set; } = Array.Empty<string>();
    public string EvidenceRefs { get; set; } = "[]"; // jsonb
    public DateTimeOffset GeneratedAt { get; set; }
}
