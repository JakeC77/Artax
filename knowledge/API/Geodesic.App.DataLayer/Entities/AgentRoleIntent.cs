namespace Geodesic.App.DataLayer.Entities;

/// <summary>
/// Join table: which intents an agent role is allowed to execute.
/// </summary>
public class AgentRoleIntent
{
    public Guid AgentRoleId { get; set; }
    public Guid IntentId { get; set; }
}
