# SnapQuote API 📱

**Text your estimate. Get a pro quote link.**

C# / Azure serverless backend for SnapQuote.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ClickSend     │────▶│  Azure Function │────▶│  Azure OpenAI   │
│   (SMS In)      │     │  (Webhook)      │     │  (Parse Text)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ClickSend     │◀────│  PDF Generator  │◀────│  Azure Blob     │
│   (SMS Out)     │     │  (QuestPDF)     │     │  (Storage)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Azure SQL     │
                        │  (Quote History)│
                        └─────────────────┘
```

## Tech Stack

- **Runtime:** .NET 8
- **Hosting:** Azure Functions (Consumption plan)
- **SMS:** ClickSend API
- **AI:** Azure OpenAI (GPT-4o) for text parsing
- **PDF:** QuestPDF (free, modern C# PDF library)
- **Storage:** Azure Blob Storage (PDFs + logos)
- **Database:** Azure SQL (users, quotes, history)
- **Auth:** Phone number based (SMS verification)

## Project Structure

```
src/
├── SnapQuote.Api/           # Azure Functions endpoints
│   ├── Functions/
│   │   ├── SmsWebhook.cs    # ClickSend incoming SMS
│   │   ├── GetQuote.cs      # Public quote PDF endpoint
│   │   └── Health.cs        # Health check
│   └── Program.cs
│
├── SnapQuote.Core/          # Business logic
│   ├── Services/
│   │   ├── QuoteParser.cs   # AI text → line items
│   │   ├── PdfGenerator.cs  # Generate PDF quotes
│   │   └── SmsService.cs    # ClickSend integration
│   ├── Models/
│   │   ├── Quote.cs
│   │   ├── LineItem.cs
│   │   └── User.cs
│   └── Interfaces/
│
└── SnapQuote.Infrastructure/ # Data access
    ├── Data/
    │   └── SnapQuoteDbContext.cs
    └── Repositories/
```

## Flow

1. **SMS In** → ClickSend webhook hits Azure Function
2. **Parse** → Azure OpenAI extracts line items from freeform text
3. **Generate** → QuestPDF creates professional PDF
4. **Store** → PDF uploaded to Blob Storage
5. **Reply** → ClickSend sends link back to user

## Local Development

```bash
# Restore packages
dotnet restore

# Run locally
func start

# Test webhook
curl -X POST http://localhost:7071/api/sms/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "+15551234567", "body": "Kitchen remodel - cabinets $3500, countertops $2200, labor $1800"}'
```

## Environment Variables

```
CLICKSEND_API_KEY=xxx
CLICKSEND_API_SECRET=xxx
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_KEY=xxx
AZURE_STORAGE_CONNECTION=xxx
SQL_CONNECTION_STRING=xxx
```

## Deploy

```bash
# Build
dotnet publish -c Release

# Deploy to Azure
func azure functionapp publish snapquote-api
```
