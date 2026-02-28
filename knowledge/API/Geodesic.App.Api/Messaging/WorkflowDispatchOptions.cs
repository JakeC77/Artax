namespace Geodesic.App.Api.Messaging;

/// <summary>
/// Configuration for how workflow runs are dispatched: Service Bus (default) or Azure Container Apps Job.
/// </summary>
public class WorkflowDispatchOptions
{
    public const string SectionName = "WorkflowDispatch";

    /// <summary>Dispatch mode: "ServiceBus" or "ContainerAppsJob". Default "ServiceBus".</summary>
    public string Mode { get; set; } = "ServiceBus";

    /// <summary>Azure AD tenant ID for the subscription. Required when the subscription is in a different tenant than the default credential (avoids InvalidAuthenticationTokenTenant).</summary>
    public string? TenantId { get; set; }

    /// <summary>Azure subscription ID. Required when Mode = ContainerAppsJob.</summary>
    public string? SubscriptionId { get; set; }

    /// <summary>Azure resource group containing the Container Apps Job. Required when Mode = ContainerAppsJob.</summary>
    public string? ResourceGroup { get; set; }

    /// <summary>Container Apps Job resource name. Required when Mode = ContainerAppsJob.</summary>
    public string? JobName { get; set; }

    /// <summary>Blob container for workflow payloads (PAYLOAD_URL). Required when Mode = ContainerAppsJob.</summary>
    public string? PayloadBlobContainer { get; set; }

    /// <summary>SAS URL expiry for payload blob in minutes. Default 60.</summary>
    public int PayloadSasExpiryMinutes { get; set; } = 60;

    /// <summary>Name of the container in the Job template (e.g. "main"). Used in Start request body. Default "main".</summary>
    public string ContainerName { get; set; } = "main";

    /// <summary>Container image for the Start request (e.g. "myacr.azurecr.io/geodesic-ai:latest"). Required by Azure Jobs Start API when Mode = ContainerAppsJob.</summary>
    public string? ContainerImage { get; set; }
}
