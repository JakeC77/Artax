
namespace Geodesic.App.DataLayer.Entities;
public class WorkspaceItem
{
    public Guid WorkspaceItemId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string GraphNodeId { get; set; } = default!;
    public string? GraphEdgeId { get; set; } // nullable
    public string[] Labels { get; set; } = Array.Empty<string>();
    public Guid PinnedBy { get; set; }
    public DateTimeOffset PinnedAt { get; set; }
}
