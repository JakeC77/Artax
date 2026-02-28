
namespace Geodesic.App.DataLayer.Entities;
public class WorkspaceMember
{
    public Guid WorkspaceId { get; set; }
    public Guid UserId { get; set; }
    public string Role { get; set; } = "viewer"; // owner|editor|viewer
    public DateTimeOffset AddedAt { get; set; }
}
