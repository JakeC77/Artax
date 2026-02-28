using Azure;
using Azure.Identity;
using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;
using Microsoft.Extensions.Options;

namespace Geodesic.App.Api.Storage;

public sealed class AzureBlobFileStorage : IFileStorage
{
    private readonly AzureStorageOptions _options;

    public AzureBlobFileStorage(IOptions<AzureStorageOptions> options)
    {
        _options = options.Value;
    }

    private BlobServiceClient CreateServiceClient()
    {
        if (!string.IsNullOrWhiteSpace(_options.ConnectionString))
        {
            return new BlobServiceClient(_options.ConnectionString);
        }
        if (!string.IsNullOrWhiteSpace(_options.ServiceUri))
        {
            return new BlobServiceClient(new Uri(_options.ServiceUri), new DefaultAzureCredential());
        }
        throw new InvalidOperationException("Azure Storage not configured. Set AzureStorage:ConnectionString or AzureStorage:ServiceUri.");
    }

    public async Task<Uri> UploadAsync(string container, string blobPath, Stream content, string? contentType, CancellationToken ct)
    {
        var svc = CreateServiceClient();
        var containerClient = svc.GetBlobContainerClient(container);
        await containerClient.CreateIfNotExistsAsync(PublicAccessType.None, cancellationToken: ct);
        var blob = containerClient.GetBlobClient(blobPath);
        var headers = new BlobHttpHeaders();
        if (!string.IsNullOrWhiteSpace(contentType)) headers.ContentType = contentType;
        await blob.UploadAsync(content, new BlobUploadOptions { HttpHeaders = headers }, ct);
        return blob.Uri;
    }

    public async Task<bool> DeleteAsync(string container, string blobPath, CancellationToken ct)
    {
        var svc = CreateServiceClient();
        var containerClient = svc.GetBlobContainerClient(container);
        var blob = containerClient.GetBlobClient(blobPath);
        var resp = await blob.DeleteIfExistsAsync(DeleteSnapshotsOption.IncludeSnapshots, conditions: null, ct);
        return resp.Value;
    }

    public async Task<string?> GetContentAsStringAsync(string container, string blobPath, CancellationToken ct)
    {
        var svc = CreateServiceClient();
        var containerClient = svc.GetBlobContainerClient(container);
        var blob = containerClient.GetBlobClient(blobPath);
        try
        {
            var result = await blob.DownloadContentAsync(ct);
            return result.Value.Content.ToString();
        }
        catch (RequestFailedException ex) when (ex.Status == 404)
        {
            return null;
        }
    }
}

