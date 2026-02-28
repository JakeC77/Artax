
namespace Geodesic.App.DataLayer.Entities;
public class Workspace
{
    public Guid WorkspaceId { get; set; }
    public Guid TenantId { get; set; }
    public Guid? CompanyId { get; set; }
    public Guid? OntologyId { get; set; }
    public Guid OwnerUserId { get; set; }
    public string Name { get; set; } = default!;
    public string? Description { get; set; }
    public string? Intent { get; set; }
    public string Visibility { get; set; } = "private"; // private|workspace|tenant
    public DateTimeOffset? BaseSnapshotTs { get; set; }
    public Guid? SetupRunId { get; set; }

    // Workspace state: draft|setup|working|action|archived
    public string State { get; set; } = "draft";

    // Setup workflow fields (only relevant when State == "setup")
    public string SetupStage { get; set; } = "intent_discovery"; // intent_discovery|data_scoping|data_review|team_building
    public string? SetupIntentPackage { get; set; } // JSONB
    public string? SetupDataScope { get; set; } // JSONB
    public string? SetupExecutionResults { get; set; } // JSONB
    public string? SetupTeamConfig { get; set; } // JSONB
    public DateTimeOffset? SetupStartedAt { get; set; }
    public DateTimeOffset? SetupCompletedAt { get; set; }

    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
