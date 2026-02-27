# SnapQuote 📱 → 📄

Text your estimate. Get a pro quote link.

## What It Does

Contractors text their estimate to (833) 515-4305. Within a minute, they get back a link to a professional PDF quote they can share with their customer.

## Quick Start

### 1. Set up environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run with Docker

```bash
docker compose up -d
```

### 3. Configure ClickSend Webhook

In your ClickSend dashboard, set up an inbound SMS webhook:
- URL: `https://your-domain.com/webhook/sms`
- Method: POST
- Format: JSON

### 4. Test it!

Text your estimate to (833) 515-4305:
```
John Smith - deck repair $450, new railing $275
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `CLICKSEND_USERNAME` | ClickSend account username | Yes |
| `CLICKSEND_API_KEY` | ClickSend API key | Yes |
| `SNAPQUOTE_NUMBER` | Your ClickSend TFN | Yes |
| `ANTHROPIC_API_KEY` | Claude API key for smart parsing | Recommended |
| `BASE_URL` | Public URL for quote links | Yes |
| `QUOTES_DIR` | Directory to store PDFs | No (default: quotes) |
| `LOGOS_DIR` | Directory to store logos | No (default: logos) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/webhook/sms` | POST | ClickSend inbound webhook |
| `/quote/{id}` | GET | Serve quote PDF |

## Conversation Flow

```
User: "deck repair 450 railing 275"
Bot:  "Got: Deck repair $450, Railing $275. Customer name for the quote?"

User: "John Smith"
Bot:  "Your quote is ready! https://... Share this link with John Smith."
```

## Development

```bash
# Install deps
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --port 8080

# Test webhook
curl -X POST http://localhost:8080/webhook/sms \
  -H "Content-Type: application/json" \
  -d '{"from": "+15551234567", "body": "John Smith deck repair 450"}'
```

## Production Deployment

1. Point a domain at this server (e.g., `snapquote.haventech.co`)
2. Set up SSL (Let's Encrypt via nginx or Caddy)
3. Update `BASE_URL` in `.env`
4. Configure ClickSend webhook to your domain

---

Built by Haven Tech Solutions
