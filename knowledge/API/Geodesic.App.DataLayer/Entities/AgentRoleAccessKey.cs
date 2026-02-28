namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Access key generated against an agent role. Secret is never stored; only hash and prefix.
/// The full secret is returned once on generation.
/// </summary>
public class AgentRoleAccessKey
{
    public Guid AccessKeyId { get; set; }
    public Guid AgentRoleId { get; set; }
    /// <summary>Hash of the secret (e.g. SHA256 hex). Never expose.</summary>
    public string KeyHash { get; set; } = default!;
    /// <summary>Short prefix for display (e.g. ge_1a2b3c4d).</summary>
    public string KeyPrefix { get; set; } = default!;
    public string? Name { get; set; }
    public DateTimeOffset CreatedOn { get; set; }
    public DateTimeOffset? ExpiresAt { get; set; }
}
