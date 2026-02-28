
namespace Geodesic.App.DataLayer.Entities;
public class OverlayNodePatch
{
    public Guid ChangesetId { get; set; }
    public string GraphNodeId { get; set; } = default!;
    public string Op { get; set; } = "upsert"; // upsert|delete
    public string Patch { get; set; } = "{}"; // jsonb
}
