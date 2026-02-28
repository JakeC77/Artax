using System.Text.Json;
using Azure.Messaging.ServiceBus;
using Geodesic.App.Api.Models;
using Microsoft.Extensions.Logging;

namespace Geodesic.App.Api.Messaging;

/// <summary>
/// Dispatches workflow events to Azure Service Bus. Returns false if Service Bus is not configured.
/// </summary>
public sealed class ServiceBusWorkflowDispatcher : IWorkflowDispatcher
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    private readonly ServiceBusSender? _sender;
    private readonly ILogger<ServiceBusWorkflowDispatcher>? _logger;

    public ServiceBusWorkflowDispatcher(
        ServiceBusSender? sender,
        ILogger<ServiceBusWorkflowDispatcher>? logger = null)
    {
        _sender = sender;
        _logger = logger;
    }

    public async Task<bool> DispatchAsync(WorkflowEventPayload payload, CancellationToken ct = default)
    {
        if (_sender is null)
            return false;

        var body = JsonSerializer.Serialize(payload, JsonOptions);
        var eventType = GetEventType(payload.WorkflowId);

        var msg = new ServiceBusMessage(BinaryData.FromString(body))
        {
            MessageId = payload.RunId.ToString(),
            Subject = eventType,
            CorrelationId = payload.RunId.ToString()
        };
        msg.ApplicationProperties.Add("eventType", eventType);
        msg.ApplicationProperties.Add("workflowId", payload.WorkflowId);
        msg.ApplicationProperties.Add("runId", payload.RunId.ToString());
        msg.ApplicationProperties.Add("workspaceId", payload.WorkspaceId.ToString());
        if (payload.Engine is { } engine)
            msg.ApplicationProperties.Add("engine", engine);

        await _sender.SendMessageAsync(msg, ct);
        _logger?.LogInformation("Workflow dispatched to Service Bus. RunId={RunId}, WorkflowId={WorkflowId}", payload.RunId, payload.WorkflowId);
        return true;
    }

    private static string GetEventType(string workflowId) =>
        workflowId switch
        {
            "ontology-conversation" => "ontology-conversation.queued",
            "data-loading" => "data-loading.queued",
            "document-graphiti" => "document-indexing.queued",
            _ => "scenario.run.created"
        };
}
