using Azure.Storage.Blobs;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace SnapQuote.Api.Functions;

public class GetQuote
{
    private readonly ILogger<GetQuote> _logger;
    private readonly BlobContainerClient _blobContainer;

    public GetQuote(ILogger<GetQuote> logger, BlobContainerClient blobContainer)
    {
        _logger = logger;
        _blobContainer = blobContainer;
    }

    [Function("GetQuote")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "q/{quoteId}")] 
        HttpRequestData req,
        string quoteId)
    {
        _logger.LogInformation("Quote requested: {QuoteId}", quoteId);

        try
        {
            var blobName = $"quotes/{quoteId}.pdf";
            var blobClient = _blobContainer.GetBlobClient(blobName);

            if (!await blobClient.ExistsAsync())
            {
                var notFound = req.CreateResponse(System.Net.HttpStatusCode.NotFound);
                await notFound.WriteStringAsync("Quote not found");
                return notFound;
            }

            var download = await blobClient.DownloadContentAsync();
            
            var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "application/pdf");
            response.Headers.Add("Content-Disposition", $"inline; filename=\"quote-{quoteId}.pdf\"");
            await response.Body.WriteAsync(download.Value.Content.ToArray());
            
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving quote {QuoteId}", quoteId);
            var error = req.CreateResponse(System.Net.HttpStatusCode.InternalServerError);
            await error.WriteStringAsync("Error retrieving quote");
            return error;
        }
    }
}
