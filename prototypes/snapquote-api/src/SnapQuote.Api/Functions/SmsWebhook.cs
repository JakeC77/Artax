using System.Text.Json;
using Azure.Storage.Blobs;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using SnapQuote.Core.Models;
using SnapQuote.Core.Services;

namespace SnapQuote.Api.Functions;

public class SmsWebhook
{
    private readonly ILogger<SmsWebhook> _logger;
    private readonly IQuoteParser _quoteParser;
    private readonly IPdfGenerator _pdfGenerator;
    private readonly BlobContainerClient _blobContainer;

    public SmsWebhook(
        ILogger<SmsWebhook> logger,
        IQuoteParser quoteParser,
        IPdfGenerator pdfGenerator,
        BlobContainerClient blobContainer)
    {
        _logger = logger;
        _quoteParser = quoteParser;
        _pdfGenerator = pdfGenerator;
        _blobContainer = blobContainer;
    }

    [Function("SmsWebhook")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "sms/webhook")] 
        HttpRequestData req)
    {
        _logger.LogInformation("SMS webhook received");

        // Parse ClickSend webhook payload
        var body = await req.ReadAsStringAsync();
        var payload = JsonSerializer.Deserialize<ClickSendWebhook>(body, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        });

        if (payload == null || string.IsNullOrEmpty(payload.Body))
        {
            var badResponse = req.CreateResponse(System.Net.HttpStatusCode.BadRequest);
            await badResponse.WriteStringAsync("Invalid payload");
            return badResponse;
        }

        var phoneNumber = payload.From ?? "unknown";
        var messageText = payload.Body;

        _logger.LogInformation("Processing SMS from {Phone}: {Text}", phoneNumber, messageText);

        try
        {
            // 1. Parse the estimate text into structured quote
            var quote = await _quoteParser.ParseAsync(phoneNumber, messageText);

            // 2. Get or create user (simplified - would normally hit DB)
            var user = new User
            {
                PhoneNumber = phoneNumber,
                BusinessName = "Your Business" // Would load from DB
            };

            // 3. Generate PDF
            var pdfBytes = _pdfGenerator.Generate(quote, user);

            // 4. Upload to blob storage
            var blobName = $"quotes/{quote.Id}.pdf";
            var blobClient = _blobContainer.GetBlobClient(blobName);
            await blobClient.UploadAsync(new BinaryData(pdfBytes), overwrite: true);

            // 5. Generate shareable link
            var baseUrl = Environment.GetEnvironmentVariable("BASE_URL") ?? "https://snapquote.azurewebsites.net";
            quote.ShareableLink = $"{baseUrl}/q/{quote.Id}";
            quote.PdfUrl = blobClient.Uri.ToString();

            // 6. Send reply via ClickSend (would call ClickSend API)
            var replyMessage = $"✅ Your quote is ready!\n\n{quote.ShareableLink}\n\nTotal: {quote.Total:C}";
            await SendSmsReplyAsync(phoneNumber, replyMessage);

            _logger.LogInformation("Quote {QuoteId} generated and sent to {Phone}", quote.Id, phoneNumber);

            var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
            await response.WriteAsJsonAsync(new { quoteId = quote.Id, link = quote.ShareableLink });
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing SMS from {Phone}", phoneNumber);

            // Send error reply
            await SendSmsReplyAsync(phoneNumber, "Sorry, we couldn't process your quote. Please try again or contact support.");

            var errorResponse = req.CreateResponse(System.Net.HttpStatusCode.InternalServerError);
            await errorResponse.WriteStringAsync("Error processing request");
            return errorResponse;
        }
    }

    private async Task SendSmsReplyAsync(string to, string message)
    {
        // ClickSend API call would go here
        var apiKey = Environment.GetEnvironmentVariable("CLICKSEND_API_KEY");
        var apiSecret = Environment.GetEnvironmentVariable("CLICKSEND_API_SECRET");

        // For now, just log - would implement actual ClickSend HTTP call
        _logger.LogInformation("Would send SMS to {To}: {Message}", to, message);

        // TODO: Implement ClickSend API call
        // POST https://rest.clicksend.com/v3/sms/send
        await Task.CompletedTask;
    }

    private class ClickSendWebhook
    {
        public string? From { get; set; }
        public string? To { get; set; }
        public string? Body { get; set; }
        public string? MessageId { get; set; }
        public DateTime? Timestamp { get; set; }
    }
}
