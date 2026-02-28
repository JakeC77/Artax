namespace Geodesic.App.DataLayer.Entities;

public class AITeam
{
    public Guid AITeamId { get; set; }
    public Guid WorkspaceId { get; set; }
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }

    public ICollection<AITeamMember> Members { get; set; } = new List<AITeamMember>();
}
