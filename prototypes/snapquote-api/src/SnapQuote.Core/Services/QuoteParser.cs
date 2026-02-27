using System.Text.Json;
using Azure;
using Azure.AI.OpenAI;
using SnapQuote.Core.Models;

namespace SnapQuote.Core.Services;

public interface IQuoteParser
{
    Task<Quote> ParseAsync(string phoneNumber, string rawText);
}

public class QuoteParser : IQuoteParser
{
    private readonly OpenAIClient _openAiClient;
    private readonly string _deploymentName;

    public QuoteParser(string endpoint, string apiKey, string deploymentName = "gpt-4o")
    {
        _openAiClient = new OpenAIClient(new Uri(endpoint), new AzureKeyCredential(apiKey));
        _deploymentName = deploymentName;
    }

    public async Task<Quote> ParseAsync(string phoneNumber, string rawText)
    {
        var systemPrompt = @"You are a quote parsing assistant. Extract line items from the user's text message.
Return a JSON object with this structure:
{
  ""customerName"": ""string or null"",
  ""lineItems"": [
    { ""description"": ""string"", ""quantity"": number, ""unitPrice"": number }
  ],
  ""notes"": ""string or null""
}

Rules:
- Extract each distinct item/service as a line item
- If quantity isn't specified, assume 1
- Parse prices from various formats ($1,500 / 1500 / $1.5k)
- Keep descriptions concise but clear
- If customer name is mentioned, extract it
- Put any extra context in notes

Example input: ""Kitchen remodel for John - cabinets $3500, countertops $2200, labor $1800""
Example output: {""customerName"":""John"",""lineItems"":[{""description"":""Cabinets"",""quantity"":1,""unitPrice"":3500},{""description"":""Countertops"",""quantity"":1,""unitPrice"":2200},{""description"":""Labor"",""quantity"":1,""unitPrice"":1800}],""notes"":""Kitchen remodel""}";

        var chatOptions = new ChatCompletionsOptions
        {
            DeploymentName = _deploymentName,
            Messages =
            {
                new ChatRequestSystemMessage(systemPrompt),
                new ChatRequestUserMessage(rawText)
            },
            Temperature = 0.1f,
            ResponseFormat = ChatCompletionsResponseFormat.JsonObject
        };

        var response = await _openAiClient.GetChatCompletionsAsync(chatOptions);
        var content = response.Value.Choices[0].Message.Content;

        var parsed = JsonSerializer.Deserialize<ParsedQuote>(content, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        });

        return new Quote
        {
            PhoneNumber = phoneNumber,
            RawText = rawText,
            CustomerName = parsed?.CustomerName,
            Notes = parsed?.Notes,
            LineItems = parsed?.LineItems?.Select(li => new LineItem
            {
                Description = li.Description,
                Quantity = li.Quantity,
                UnitPrice = li.UnitPrice
            }).ToList() ?? new List<LineItem>()
        };
    }

    private class ParsedQuote
    {
        public string? CustomerName { get; set; }
        public List<ParsedLineItem>? LineItems { get; set; }
        public string? Notes { get; set; }
    }

    private class ParsedLineItem
    {
        public string Description { get; set; } = string.Empty;
        public decimal Quantity { get; set; } = 1;
        public decimal UnitPrice { get; set; }
    }
}
