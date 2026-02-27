using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace SnapQuote.Core.Services;

public interface ISmsService
{
    Task SendAsync(string to, string message);
}

public class ClickSendSmsService : ISmsService
{
    private readonly HttpClient _httpClient;
    private readonly string _fromNumber;

    public ClickSendSmsService(string apiKey, string apiSecret, string fromNumber)
    {
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri("https://rest.clicksend.com/v3/")
        };

        var authBytes = Encoding.ASCII.GetBytes($"{apiKey}:{apiSecret}");
        _httpClient.DefaultRequestHeaders.Authorization = 
            new AuthenticationHeaderValue("Basic", Convert.ToBase64String(authBytes));
        
        _fromNumber = fromNumber;
    }

    public async Task SendAsync(string to, string message)
    {
        var payload = new
        {
            messages = new[]
            {
                new
                {
                    source = "SnapQuote",
                    from = _fromNumber,
                    to = to,
                    body = message
                }
            }
        };

        var content = new StringContent(
            JsonSerializer.Serialize(payload),
            Encoding.UTF8,
            "application/json");

        var response = await _httpClient.PostAsync("sms/send", content);
        response.EnsureSuccessStatusCode();
    }
}
