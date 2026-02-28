using Geodesic.App.Api.Models;

namespace Geodesic.App.Api.Messaging;

/// <summary>
/// Dispatches a workflow run to either Azure Service Bus or an Azure Container Apps Job.
/// </summary>
public interface IWorkflowDispatcher
{
    /// <summary>
    /// Dispatches the workflow event. Returns true if dispatched, false if skipped (e.g. missing config).
    /// </summary>
    Task<bool> DispatchAsync(WorkflowEventPayload payload, CancellationToken ct = default);
}
