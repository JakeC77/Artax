# DejaView Stripe Setup

## Quick Path (Payment Links - No Backend Required)

Stripe Payment Links let us start collecting money with ZERO backend code.

### Steps

1. Create Stripe account
2. Create products and prices in Dashboard
3. Create Payment Links (no code needed)
4. Embed links in landing page pricing buttons
5. Add webhook for auto-provisioning API keys

### Products

**DejaView Pro** - 2/mo
  - Hosted graph
  - Web UI
  - Browser extension
  - Integrations
  - 10K entities

**DejaView API** - /bin/bash.01/query after 1K free
  - REST API
  - Python SDK
  - Multi-tenant
  - Webhooks

### Webhook Auto-Provisioning

When someone pays, Stripe sends a webhook. We:
1. Generate a unique API key (dv_xxxx)
2. Create their isolated graph in Neo4j
3. Email them their API key + getting started guide
4. They are live in < 60 seconds

### Webhook Endpoint

Add POST /webhooks/stripe to api.py (code in api.py comments)

### Environment Variables


