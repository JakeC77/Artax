# SnapQuote - Status Report
**Date:** February 27, 2026  
**Status:** MVP Functional (with carrier limitations)

## What It Does
Contractors text their estimate to (833) 515-4305 → get back a link to a professional PDF quote.

## What's Working ✅

### Core Flow
- **SMS Intake:** Polling ClickSend API for inbound messages
- **Estimate Parsing:** Regex-based extraction of customer name, line items, prices
- **PDF Generation:** Professional quotes via ReportLab (customer name, itemized list, totals, branding)
- **SMS Reply:** Sends quote link back to contractor

### Infrastructure
- **Server:** FastAPI on DO droplet (port 8080)
- **Tunnel:** localhost.run for external access (DO firewall blocks 8080 directly)
- **Current URL:** https://5b88863af0b662.lhr.life

### Example Flow
```
Contractor texts: "Bob Jones - deck repair 450, railing 200"
System parses: customer=Bob Jones, items=[{deck repair, $450}, {railing, $200}]
PDF generated: /quote/79000be5
Reply sent: "Quote ready for Bob Jones! Total: $650. Code: 79000be5"
```

## Known Issues ⚠️

### ClickSend Content Filtering
- **Problem:** Messages containing URLs get flagged as "risky" and held for review
- **Impact:** 5-10 minute delay on replies, some messages cancelled
- **Workaround:** Removed URLs from replies; just send quote code
- **Fix needed:** Contact ClickSend to whitelist domain, or use different SMS provider

### DO Firewall
- **Problem:** Port 8080 not accessible externally
- **Workaround:** Using localhost.run tunnel
- **Fix needed:** Open port 8080 in DO Networking → Firewalls, or set up nginx on port 80

### Inbound Message Delays
- **Problem:** Inbound SMS also batched/delayed by ClickSend
- **Impact:** Messages arrive in batches every few minutes
- **Fix needed:** ClickSend support or different provider

## File Structure
```
prototypes/snapquote/
├── app/
│   ├── main.py      # FastAPI app, webhook endpoint
│   ├── sms.py       # SMS handling, ClickSend integration
│   ├── parser.py    # Estimate parsing (regex + LLM)
│   ├── pdf_gen.py   # PDF generation
│   ├── state.py     # Conversation state machine
│   └── logos.py     # Logo storage per phone
├── run_poller.py    # Main polling loop
├── quotes/          # Generated PDFs
├── .env             # Credentials (not in git)
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Credentials Required
- `CLICKSEND_USERNAME` - ClickSend account
- `CLICKSEND_API_KEY` - ClickSend API key
- `ANTHROPIC_API_KEY` - For smart parsing (optional, falls back to regex)

## Running It

### Start the server (serves PDFs):
```bash
cd ~/.openclaw/workspace/artax/prototypes/snapquote
source .venv/bin/activate && source .env
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Start the poller (processes SMS):
```bash
python -u run_poller.py
```

### Start tunnel (if DO firewall blocks 8080):
```bash
ssh -R 80:localhost:8080 nokey@localhost.run
```

## Next Steps

### Immediate
1. [ ] Contact ClickSend support re: URL filtering / whitelist domain
2. [ ] Open port 8080 in DO firewall OR set up nginx reverse proxy
3. [ ] Register a proper domain (e.g., snapquote.haventech.co)

### Soon
1. [ ] Add LLM parsing back (currently regex-only due to model issues)
2. [ ] Logo upload flow (MMS handling)
3. [ ] Email fallback for quote delivery
4. [ ] Quote history/tracking dashboard

### Later
1. [ ] User accounts / contractor profiles
2. [ ] Stripe integration for billing
3. [ ] Quote acceptance / e-signature
4. [ ] Multiple templates

## Marketing Site
**Live:** https://jakec77.github.io/Artax/sites/snapquote/

---
*Built by Artax 🐴 for Haven Tech Solutions*
