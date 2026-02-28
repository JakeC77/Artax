
namespace Geodesic.App.DataLayer.Entities;
public class OverlayEdgePatch
{
    public Guid ChangesetId { get; set; }
    public string GraphEdgeId { get; set; } = default!;
    public string Op { get; set; } = "upsert";
    public string Patch { get; set; } = "{}"; // jsonb
}
