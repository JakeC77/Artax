using Azure.Messaging.ServiceBus;
using Microsoft.Extensions.Options;

namespace Geodesic.App.Api.Messaging;

public class ServiceBusOptions
{
    public string? ConnectionString { get; set; }
    public string? QueueName { get; set; }
}

public sealed class AzureScenarioRunEventPublisher : IScenarioRunEventPublisher, IAsyncDisposable
{
    private readonly ServiceBusClient _client;
    private readonly string _queueName;

    public AzureScenarioRunEventPublisher(IOptions<ServiceBusOptions> options)
    {
        var conn = options.Value.ConnectionString;
        var queue = options.Value.QueueName;
        if (string.IsNullOrWhiteSpace(conn))
            throw new InvalidOperationException("Azure Service Bus connection string is not configured.");
        if (string.IsNullOrWhiteSpace(queue))
            throw new InvalidOperationException("Azure Service Bus queue name is not configured.");
        _client = new ServiceBusClient(conn);
        _queueName = queue;
    }

    public async Task PublishScenarioRunCreatedAsync(ScenarioRunCreatedEvent evt, CancellationToken ct)
    {
        var sender = _client.CreateSender(_queueName);
        try
        {
            var message = new ServiceBusMessage(evt.ToJson())
            {
                ContentType = "application/json",
                Subject = "scenario.run.created"
            };
            message.ApplicationProperties["eventType"] = "scenario.run.created";
            message.ApplicationProperties["runId"] = evt.RunId.ToString();
            if (evt.ScenarioId.HasValue)
                message.ApplicationProperties["scenarioId"] = evt.ScenarioId.Value.ToString();
            message.ApplicationProperties["workspaceId"] = evt.WorkspaceId.ToString();
            if (evt.RelatedChangesetId.HasValue)
                message.ApplicationProperties["changesetId"] = evt.RelatedChangesetId.Value.ToString();

            await sender.SendMessageAsync(message, ct);
        }
        finally
        {
            await sender.DisposeAsync();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await _client.DisposeAsync();
    }
}

