using System.Text.Json;
using Azure.Storage.Blobs;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using SnapQuote.Core.Models;
using SnapQuote.Core.Services;
using SnapQuote.Infrastructure.Repositories;

namespace SnapQuote.Api.Functions;

public class SmsWebhook
{
    private readonly ILogger<SmsWebhook> _logger;
    private readonly IQuoteParser _quoteParser;
    private readonly IPdfGenerator _pdfGenerator;
    private readonly ISmsService _smsService;
    private readonly ILogoService _logoService;
    private readonly ISubscriptionService _subscriptionService;
    private readonly IUserRepository _userRepository;
    private readonly IQuoteRepository _quoteRepository;
    private readonly BlobContainerClient _blobContainer;

    public SmsWebhook(
        ILogger<SmsWebhook> logger,
        IQuoteParser quoteParser,
        IPdfGenerator pdfGenerator,
        ISmsService smsService,
        ILogoService logoService,
        ISubscriptionService subscriptionService,
        IUserRepository userRepository,
        IQuoteRepository quoteRepository,
        BlobContainerClient blobContainer)
    {
        _logger = logger;
        _quoteParser = quoteParser;
        _pdfGenerator = pdfGenerator;
        _smsService = smsService;
        _logoService = logoService;
        _subscriptionService = subscriptionService;
        _userRepository = userRepository;
        _quoteRepository = quoteRepository;
        _blobContainer = blobContainer;
    }

    [Function("SmsWebhook")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "post", Route = "sms/webhook")]
        HttpRequestData req)
    {
        _logger.LogInformation("SMS webhook received");

        var body = await req.ReadAsStringAsync();
        var payload = JsonSerializer.Deserialize<ClickSendWebhook>(body, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        });

        if (payload == null || string.IsNullOrEmpty(payload.Body))
        {
            return await CreateResponse(req, System.Net.HttpStatusCode.BadRequest, "Invalid payload");
        }

        var phoneNumber = NormalizePhoneNumber(payload.From ?? "");
        var messageText = payload.Body.Trim();

        _logger.LogInformation("Processing SMS from {Phone}: {Text}", phoneNumber, messageText);

        try
        {
            // Get or create user
            var user = await _userRepository.GetOrCreateAsync(phoneNumber);

            // Check if this is a logo upload (MMS with image)
            if (payload.MediaUrl != null && IsImageUrl(payload.MediaUrl))
            {
                await HandleLogoUpload(user, payload.MediaUrl);
                await _smsService.SendAsync(phoneNumber, 
                    "✅ Logo saved! It'll appear on all your quotes from now on.");
                return await CreateResponse(req, System.Net.HttpStatusCode.OK, new { action = "logo_saved" });
            }

            // Check subscription limits
            if (!_subscriptionService.CanCreateQuote(user))
            {
                var remaining = _subscriptionService.GetRemainingQuotes(user);
                await _smsService.SendAsync(phoneNumber,
                    $"You've used all {remaining} free quotes this month. Reply UPGRADE to unlock unlimited quotes for $19/mo.");
                return await CreateResponse(req, System.Net.HttpStatusCode.OK, new { action = "limit_reached" });
            }

            // Check for commands
            if (messageText.ToUpper() == "UPGRADE")
            {
                // TODO: Send payment link
                await _smsService.SendAsync(phoneNumber,
                    "Upgrade to Pro for unlimited quotes: https://snapquote.com/upgrade");
                return await CreateResponse(req, System.Net.HttpStatusCode.OK, new { action = "upgrade_link" });
            }

            if (messageText.ToUpper() == "HELP")
            {
                await _smsService.SendAsync(phoneNumber,
                    "📱 SnapQuote Help:\n\n" +
                    "• Text your estimate to create a quote\n" +
                    "• Send a photo of your logo to brand quotes\n" +
                    "• Reply UPGRADE for unlimited quotes\n" +
                    "• Reply HISTORY for recent quotes");
                return await CreateResponse(req, System.Net.HttpStatusCode.OK, new { action = "help" });
            }

            // Parse the estimate
            var quote = await _quoteParser.ParseAsync(phoneNumber, messageText);
            quote.UserId = user.Id.ToString();

            // Generate PDF
            var pdfBytes = _pdfGenerator.Generate(quote, user);

            // Upload to blob storage
            var blobName = $"quotes/{quote.Id}.pdf";
            var blobClient = _blobContainer.GetBlobClient(blobName);
            await blobClient.UploadAsync(new BinaryData(pdfBytes), overwrite: true);

            // Set URLs
            var baseUrl = Environment.GetEnvironmentVariable("BASE_URL") ?? "https://snapquote.azurewebsites.net";
            quote.ShareableLink = $"{baseUrl}/q/{quote.Id}";
            quote.PdfUrl = blobClient.Uri.ToString();

            // Save to database
            await _quoteRepository.CreateAsync(quote);
            await _userRepository.IncrementQuoteCountAsync(user.Id);

            // Send reply
            var remaining = _subscriptionService.GetRemainingQuotes(user);
            var remainingText = user.Tier == UserTier.Free ? $"\n\n({remaining} free quotes left this month)" : "";
            
            await _smsService.SendAsync(phoneNumber,
                $"✅ Quote ready!\n\n" +
                $"🔗 {quote.ShareableLink}\n\n" +
                $"Total: {quote.Total:C}{remainingText}");

            _logger.LogInformation("Quote {QuoteId} created for {Phone}", quote.Id, phoneNumber);

            return await CreateResponse(req, System.Net.HttpStatusCode.OK, new
            {
                quoteId = quote.Id,
                link = quote.ShareableLink,
                total = quote.Total
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing SMS from {Phone}", phoneNumber);
            await _smsService.SendAsync(phoneNumber,
                "Sorry, we couldn't process your quote. Please try again or reply HELP for assistance.");
            return await CreateResponse(req, System.Net.HttpStatusCode.InternalServerError, "Error processing request");
        }
    }

    private async Task HandleLogoUpload(User user, string mediaUrl)
    {
        using var httpClient = new HttpClient();
        var imageBytes = await httpClient.GetByteArrayAsync(mediaUrl);
        var logoUrl = await _logoService.UploadLogoAsync(user.Id.ToString(), imageBytes, "image/png");
        user.LogoUrl = logoUrl;
        await _userRepository.UpdateAsync(user);
    }

    private static string NormalizePhoneNumber(string phone)
    {
        // Remove all non-digits, ensure +1 prefix for US
        var digits = new string(phone.Where(char.IsDigit).ToArray());
        if (digits.Length == 10)
            digits = "1" + digits;
        return "+" + digits;
    }

    private static bool IsImageUrl(string url)
    {
        var lower = url.ToLower();
        return lower.Contains(".jpg") || lower.Contains(".jpeg") ||
               lower.Contains(".png") || lower.Contains(".gif") ||
               lower.Contains("image");
    }

    private static async Task<HttpResponseData> CreateResponse(
        HttpRequestData req, System.Net.HttpStatusCode status, object body)
    {
        var response = req.CreateResponse(status);
        if (body is string str)
            await response.WriteStringAsync(str);
        else
            await response.WriteAsJsonAsync(body);
        return response;
    }

    private class ClickSendWebhook
    {
        public string? From { get; set; }
        public string? To { get; set; }
        public string? Body { get; set; }
        public string? MessageId { get; set; }
        public string? MediaUrl { get; set; }
        public DateTime? Timestamp { get; set; }
    }
}
