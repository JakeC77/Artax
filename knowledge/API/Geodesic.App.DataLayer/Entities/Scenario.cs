
namespace Geodesic.App.DataLayer.Entities;
public class Scenario
{
    public Guid ScenarioId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string Name { get; set; } = default!;
    public string? HeaderText { get; set; }
    public string? MainText { get; set; }
    public Guid? RelatedChangesetId { get; set; }
    public Guid CreatedBy { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
}
