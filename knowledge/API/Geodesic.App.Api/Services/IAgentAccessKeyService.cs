using Geodesic.App.DataLayer.Entities;

namespace Geodesic.App.Api.Services;

/// <summary>
/// Validates agent role access keys and resolves the associated role.
/// Used by REST-style intent-execution endpoints for third-party agents.
/// </summary>
public interface IAgentAccessKeyService
{
    /// <summary>
    /// Validates the raw access key (e.g. from Authorization: Bearer or X-Api-Key).
    /// Returns the agent role and key metadata if the key is valid and not expired; otherwise null.
    /// </summary>
    Task<(AgentRole Role, AgentRoleAccessKey KeyMetadata)?> ValidateAccessKeyAsync(string rawKey, CancellationToken ct = default);
}
