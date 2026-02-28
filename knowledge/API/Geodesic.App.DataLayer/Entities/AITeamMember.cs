namespace Geodesic.App.DataLayer.Entities;

public class AITeamMember
{
    public Guid AITeamMemberId { get; set; }
    public Guid AITeamId { get; set; }
    public string AgentId { get; set; } = default!;
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public string Role { get; set; } = "worker"; // conductor|worker
    public string? SystemPrompt { get; set; }
    public string? Model { get; set; }
    public decimal? Temperature { get; set; }
    public int? MaxTokens { get; set; }
    public string[] Tools { get; set; } = Array.Empty<string>();
    public string[] Expertise { get; set; } = Array.Empty<string>();
    public string? CommunicationStyle { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }

    public AITeam? Team { get; set; }
}

