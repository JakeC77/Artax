using System.Text.Json;

namespace Geodesic.App.Api.Messaging;

public record ScenarioRunCreatedEvent
{
    public Guid TenantId { get; init; }
    public Guid WorkspaceId { get; init; }
    public Guid? ScenarioId { get; init; }
    public Guid RunId { get; init; }
    public Guid? RelatedChangesetId { get; init; }
    public string Engine { get; init; } = "";
    public string Inputs { get; init; } = "{}";
    public string? Prompt { get; init; }
    public string Status { get; init; } = "queued";
    public DateTimeOffset RequestedAt { get; init; } = DateTimeOffset.UtcNow;

    public string ToJson() => JsonSerializer.Serialize(this);
}

public interface IScenarioRunEventPublisher
{
    Task PublishScenarioRunCreatedAsync(ScenarioRunCreatedEvent evt, CancellationToken ct);
}

