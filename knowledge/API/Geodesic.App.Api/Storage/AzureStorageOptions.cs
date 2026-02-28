namespace Geodesic.App.Api.Storage;

public class AzureStorageOptions
{
    public string? ConnectionString { get; set; }
    public string? ServiceUri { get; set; } // e.g., https://account.blob.core.windows.net
    public string? AttachmentsContainer { get; set; }
}

