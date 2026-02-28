using HotChocolate;

namespace Geodesic.App.Api.Storage;

public interface IFileStorage
{
    Task<Uri> UploadAsync(string container, string blobPath, Stream content, string? contentType, CancellationToken ct);
    Task<bool> DeleteAsync(string container, string blobPath, CancellationToken ct);
    /// <summary>Returns the blob's UTF-8 content as a string, or null if the blob does not exist.</summary>
    Task<string?> GetContentAsStringAsync(string container, string blobPath, CancellationToken ct);
}

