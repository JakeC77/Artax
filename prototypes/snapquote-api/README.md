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
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Azure SQL      │     │  PDF Generator  │     │  Azure Blob     │
│  (Users/Quotes) │     │  (QuestPDF)     │     │  (Storage)      │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   ClickSend     │
                        │   (SMS Out)     │
                        └─────────────────┘
```

## Features

- ✅ **SMS-to-Quote** — Text an estimate, get a PDF link back
- ✅ **AI Parsing** — Azure OpenAI extracts line items from freeform text
- ✅ **Professional PDFs** — QuestPDF generates branded quotes
- ✅ **Logo Support** — MMS a photo to brand your quotes
- ✅ **User Tracking** — Phone-based accounts, no signup required
- ✅ **Subscription Tiers** — Free (5/mo) and Pro (unlimited)
- ✅ **Quote History** — Track all quotes by user
- ✅ **Shareable Links** — Public URLs for customer viewing

## Tech Stack

- **Runtime:** .NET 8
- **Hosting:** Azure Functions (Isolated Worker)
- **SMS:** ClickSend API
- **AI:** Azure OpenAI (GPT-4o)
- **PDF:** QuestPDF
- **Storage:** Azure Blob Storage
- **Database:** Azure SQL + Entity Framework Core

## Project Structure

```
src/
├── SnapQuote.Api/              # Azure Functions
│   ├── Functions/
│   │   ├── SmsWebhook.cs       # Main webhook - processes incoming SMS
│   │   ├── GetQuote.cs         # Public quote view endpoint
│   │   └── QuoteHistory.cs     # User's quote history
│   └── Program.cs              # DI configuration
│
├── SnapQuote.Core/             # Business Logic
│   ├── Models/
│   │   ├── Quote.cs            # Quote model + line items
│   │   └── User.cs             # User model + tiers
│   └── Services/
│       ├── QuoteParser.cs      # AI text → structured quote
│       ├── PdfGenerator.cs     # Quote → PDF
│       ├── SmsService.cs       # ClickSend integration
│       ├── LogoService.cs      # Logo upload/storage
│       └── SubscriptionService.cs  # Usage limits
│
└── SnapQuote.Infrastructure/   # Data Access
    ├── Data/
    │   └── SnapQuoteDbContext.cs
    └── Repositories/
        ├── UserRepository.cs
        └── QuoteRepository.cs
```

## SMS Commands

Users can text these commands:

| Command | Action |
|---------|--------|
| `HELP` | Show help message |
| `UPGRADE` | Get Pro subscription link |
| `HISTORY` | (Coming soon) Get recent quotes |
| `[any text]` | Create a quote from the estimate |
| `[image]` | Save as logo for future quotes |

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/sms/webhook` | ClickSend incoming SMS webhook |
| GET | `/api/q/{quoteId}` | View/download quote PDF |
| GET | `/api/quotes/{phoneNumber}` | Get user's quote history |

## Local Development

```bash
# Prerequisites
# - .NET 8 SDK
# - Azure Functions Core Tools
# - Azure Storage Emulator (or Azurite)
# - SQL Server LocalDB

# Clone and restore
cd prototypes/snapquote-api
dotnet restore

# Create database
dotnet ef database update --project src/SnapQuote.Infrastructure

# Run locally
cd src/SnapQuote.Api
func start

# Test webhook
curl -X POST http://localhost:7071/api/sms/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "+15551234567", "body": "Kitchen remodel for John - cabinets $3500, countertops $2200, labor $1800"}'
```

## Environment Variables

```bash
# Database
SQL_CONNECTION_STRING=Server=...;Database=SnapQuote;...

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_KEY=xxx
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure Storage
AZURE_STORAGE_CONNECTION=DefaultEndpointsProtocol=https;...
BLOB_CONTAINER_NAME=snapquote

# ClickSend
CLICKSEND_API_KEY=xxx
CLICKSEND_API_SECRET=xxx
SMS_FROM_NUMBER=+15551234567

# App
BASE_URL=https://snapquote.azurewebsites.net
```

## Deploy to Azure

```bash
# Create resources (one-time)
az group create -n snapquote-rg -l westus2
az storage account create -n snapquotestorage -g snapquote-rg
az functionapp create -n snapquote-api -g snapquote-rg --consumption-plan-location westus2 --storage-account snapquotestorage --functions-version 4 --runtime dotnet-isolated

# Deploy
func azure functionapp publish snapquote-api

# Configure ClickSend webhook
# Point ClickSend inbound webhook to: https://snapquote-api.azurewebsites.net/api/sms/webhook
```

## Pricing Model

| Tier | Price | Quotes/Month |
|------|-------|--------------|
| Free | $0 | 5 |
| Pro | $19/mo | Unlimited |
| Enterprise | Custom | Custom |

---

*Built by Artax 🐴 for Haven Tech Solutions*
