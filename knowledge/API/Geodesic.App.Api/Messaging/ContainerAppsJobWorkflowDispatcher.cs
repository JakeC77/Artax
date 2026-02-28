using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Azure.Core;
using Azure.Identity;
using Azure.Storage.Blobs;
using Azure.Storage.Sas;
using Geodesic.App.Api.Models;
using Geodesic.App.Api.Storage;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace Geodesic.App.Api.Messaging;

/// <summary>
/// Dispatches workflow events by starting an Azure Container Apps Job with PAYLOAD_URL (blob SAS).
/// Requires WorkflowDispatch:Mode = ContainerAppsJob and Azure Storage ConnectionString for SAS.
/// </summary>
public sealed class ContainerAppsJobWorkflowDispatcher : IWorkflowDispatcher
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    private const string ArmResourceScope = "https://management.azure.com/.default";
    private const string StartJobApiVersion = "2025-07-01";

    private readonly WorkflowDispatchOptions _options;
    private readonly AzureStorageOptions _storageOptions;
    private readonly TokenCredential _credential;
    private readonly ILogger<ContainerAppsJobWorkflowDispatcher>? _logger;

    public ContainerAppsJobWorkflowDispatcher(
        IOptions<WorkflowDispatchOptions> options,
        IOptions<AzureStorageOptions> storageOptions,
        TokenCredential credential,
        ILogger<ContainerAppsJobWorkflowDispatcher>? logger = null)
    {
        _options = options.Value;
        _storageOptions = storageOptions.Value;
        _credential = credential;
        _logger = logger;
    }

    public async Task<bool> DispatchAsync(WorkflowEventPayload payload, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(_options.SubscriptionId) ||
            string.IsNullOrWhiteSpace(_options.ResourceGroup) ||
            string.IsNullOrWhiteSpace(_options.JobName) ||
            string.IsNullOrWhiteSpace(_options.PayloadBlobContainer) ||
            string.IsNullOrWhiteSpace(_options.ContainerImage))
        {
            _logger?.LogWarning("Container Apps Job not fully configured; missing SubscriptionId, ResourceGroup, JobName, PayloadBlobContainer, or ContainerImage.");
            return false;
        }

        if (string.IsNullOrWhiteSpace(_storageOptions.ConnectionString))
        {
            _logger?.LogWarning("Azure Storage ConnectionString is required for ContainerAppsJob mode (SAS generation).");
            return false;
        }

        var json = JsonSerializer.Serialize(payload, JsonOptions);
        var blobPath = $"{payload.TenantId:N}/{payload.RunId:N}.json";

        var blobServiceClient = new BlobServiceClient(_storageOptions.ConnectionString);
        var containerClient = blobServiceClient.GetBlobContainerClient(_options.PayloadBlobContainer);
        await containerClient.CreateIfNotExistsAsync(cancellationToken: ct);

        var blobClient = containerClient.GetBlobClient(blobPath);
        using var stream = new MemoryStream(Encoding.UTF8.GetBytes(json));
        await blobClient.UploadAsync(stream, overwrite: true, ct);

        if (!blobClient.CanGenerateSasUri)
        {
            _logger?.LogError("Blob client cannot generate SAS (requires connection string with key).");
            return false;
        }

        var expiresOn = DateTimeOffset.UtcNow.AddMinutes(_options.PayloadSasExpiryMinutes);
        var sasUri = blobClient.GenerateSasUri(BlobSasPermissions.Read, expiresOn);

        var startUrl = $"https://management.azure.com/subscriptions/{_options.SubscriptionId}/resourceGroups/{_options.ResourceGroup}/providers/Microsoft.App/jobs/{_options.JobName}/start?api-version={StartJobApiVersion}";

        var tokenRequestContext = new TokenRequestContext(new[] { ArmResourceScope });
        var token = await _credential.GetTokenAsync(tokenRequestContext, ct);

        using var httpClient = new HttpClient();
        // Request body per Azure Jobs Start API 2025-07-01: containers with name, image, command, args, env
        var requestBody = new
        {
            containers = new[]
            {
                new
                {
                    name = _options.ContainerName ?? "main",
                    image = _options.ContainerImage!.Trim(),
                    command = new[] { "python" },
                    args = new[] { "-m", "app.job_entrypoint" },
                    env = new[]
                    {
                        new { name = "PAYLOAD_URL", value = sasUri.ToString() },
                        new { name = "RUN_AS_JOB", value = "true" },
                        new { name = "WORKSPACE_MOUNT_PATH", value = "/mnt/workspace" }
                    }
                }
            }
        };

        using var request = new HttpRequestMessage(HttpMethod.Post, startUrl);
        request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token.Token);
        request.Content = JsonContent.Create(requestBody);

        var response = await httpClient.SendAsync(request, ct);

        if (response.IsSuccessStatusCode || response.StatusCode == System.Net.HttpStatusCode.Accepted)
        {
            _logger?.LogInformation(
                "Container Apps Job start requested. RunId={RunId}, WorkflowId={WorkflowId}, Status={Status}",
                payload.RunId, payload.WorkflowId, response.StatusCode);
            return true;
        }

        var errorBody = await response.Content.ReadAsStringAsync(ct);
        _logger?.LogError(
            "Failed to start Container Apps Job. RunId={RunId}, Status={Status}, Response={Response}",
            payload.RunId, response.StatusCode, errorBody);
        return false;
    }
}
