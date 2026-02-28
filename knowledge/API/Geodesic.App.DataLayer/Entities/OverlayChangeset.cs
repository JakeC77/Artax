
namespace Geodesic.App.DataLayer.Entities;
public class OverlayChangeset
{
    public Guid ChangesetId { get; set; }
    public Guid WorkspaceId { get; set; }
    public Guid CreatedBy { get; set; }
    public string Status { get; set; } = "draft"; // draft|approved|rejected
    public string? Comment { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
