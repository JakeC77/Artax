namespace Geodesic.App.DataLayer.Entities;

public class WorkspaceAnalysis
{
    public Guid WorkspaceAnalysisId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string TitleText { get; set; } = default!;
    public string? BodyText { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public int Version { get; set; }
}

