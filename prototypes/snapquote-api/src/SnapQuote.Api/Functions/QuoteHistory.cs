using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using SnapQuote.Infrastructure.Repositories;

namespace SnapQuote.Api.Functions;

public class QuoteHistory
{
    private readonly ILogger<QuoteHistory> _logger;
    private readonly IUserRepository _userRepository;
    private readonly IQuoteRepository _quoteRepository;

    public QuoteHistory(
        ILogger<QuoteHistory> logger,
        IUserRepository userRepository,
        IQuoteRepository quoteRepository)
    {
        _logger = logger;
        _userRepository = userRepository;
        _quoteRepository = quoteRepository;
    }

    [Function("QuoteHistory")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Function, "get", Route = "quotes/{phoneNumber}")]
        HttpRequestData req,
        string phoneNumber)
    {
        _logger.LogInformation("Quote history requested for {Phone}", phoneNumber);

        var user = await _userRepository.GetByPhoneAsync(phoneNumber);
        if (user == null)
        {
            var notFound = req.CreateResponse(System.Net.HttpStatusCode.NotFound);
            await notFound.WriteStringAsync("User not found");
            return notFound;
        }

        var quotes = await _quoteRepository.GetByUserAsync(user.Id);

        var response = req.CreateResponse(System.Net.HttpStatusCode.OK);
        await response.WriteAsJsonAsync(new
        {
            user = new
            {
                user.PhoneNumber,
                user.BusinessName,
                user.Tier,
                user.QuotesThisMonth
            },
            quotes = quotes.Select(q => new
            {
                q.Id,
                q.CustomerName,
                q.Total,
                q.ShareableLink,
                q.CreatedAt,
                q.Status,
                lineItemCount = q.LineItems.Count
            })
        });

        return response;
    }
}
