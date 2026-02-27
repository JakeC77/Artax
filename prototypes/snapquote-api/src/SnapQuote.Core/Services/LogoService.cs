using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;

namespace SnapQuote.Core.Services;

public interface ILogoService
{
    Task<string> UploadLogoAsync(string userId, byte[] imageData, string contentType);
    Task<byte[]?> GetLogoAsync(string userId);
    string? GetLogoUrl(string userId);
}

public class BlobLogoService : ILogoService
{
    private readonly BlobContainerClient _container;
    private readonly string _baseUrl;

    public BlobLogoService(BlobContainerClient container, string baseUrl)
    {
        _container = container;
        _baseUrl = baseUrl;
    }

    public async Task<string> UploadLogoAsync(string userId, byte[] imageData, string contentType)
    {
        var blobName = $"logos/{userId}/logo.png";
        var blobClient = _container.GetBlobClient(blobName);

        await blobClient.UploadAsync(
            new BinaryData(imageData),
            new BlobUploadOptions
            {
                HttpHeaders = new BlobHttpHeaders { ContentType = contentType }
            },
            overwrite: true);

        return blobClient.Uri.ToString();
    }

    public async Task<byte[]?> GetLogoAsync(string userId)
    {
        var blobName = $"logos/{userId}/logo.png";
        var blobClient = _container.GetBlobClient(blobName);

        if (!await blobClient.ExistsAsync())
            return null;

        var download = await blobClient.DownloadContentAsync();
        return download.Value.Content.ToArray();
    }

    public string? GetLogoUrl(string userId)
    {
        return $"{_baseUrl}/logos/{userId}/logo.png";
    }
}
