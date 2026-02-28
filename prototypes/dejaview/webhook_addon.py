
# ============ Persistent API Key Store (Neo4j-backed) ============

def _load_keys_from_neo4j():
    """Load all active API keys from Neo4j into memory cache."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (u:DejaViewUser {status: 'active'})
                RETURN u.api_key as key, u.user_id as user_id,
                       u.graph_id as graph_id, u.email as email,
                       u.tier as tier
            """)
            for record in result:
                API_KEYS[record["key"]] = {
                    "user_id": record["user_id"],
                    "graph_id": record["graph_id"],
                    "email": record["email"],
                    "tier": record["tier"],
                }
        print(f"✅ Loaded {len(API_KEYS)} API keys from Neo4j")
    except Exception as e:
        print(f"⚠️  Could not load keys from Neo4j: {e}")


def _create_user(email: str, tier: str = "pro", source: str = "lemonsqueezy") -> dict:
    """Create a new user, generate API key, store in Neo4j."""
    import secrets, hashlib
    api_key = "dv_" + secrets.token_hex(24)
    user_id = "usr_" + hashlib.md5(email.encode()).hexdigest()[:12]
    graph_id = "graph_" + secrets.token_hex(8)

    with driver.session() as session:
        session.run("""
            MERGE (u:DejaViewUser {email: $email})
            SET u.api_key = $api_key,
                u.user_id = $user_id,
                u.graph_id = $graph_id,
                u.tier = $tier,
                u.source = $source,
                u.status = 'active',
                u.created_at = datetime()
            RETURN u
        """, {
            "email": email,
            "api_key": api_key,
            "user_id": user_id,
            "graph_id": graph_id,
            "tier": tier,
            "source": source,
        })

    user = {"user_id": user_id, "graph_id": graph_id, "email": email, "tier": tier}
    API_KEYS[api_key] = user
    return {"api_key": api_key, **user}


def _send_welcome_email(email: str, api_key: str):
    """Send welcome email with API key via Resend."""
    import urllib.request, urllib.parse, json, os
    resend_key = os.getenv("RESEND_API_KEY")
    if not resend_key:
        print(f"⚠️  No RESEND_API_KEY — skipping email to {email}")
        return

    payload = json.dumps({
        "from": "DejaView <hello@dejaview.io>",
        "to": [email],
        "subject": "Your DejaView API Key",
        "html": f"""
        <div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:40px 20px">
            <h1 style="font-size:28px;color:#7c5cfc">Welcome to DejaView 🔮</h1>
            <p style="color:#666;font-size:16px;line-height:1.6">
                Your personal knowledge graph is ready. Here's your API key:
            </p>
            <div style="background:#0a0e17;border-radius:12px;padding:20px;margin:24px 0">
                <code style="color:#00d4ff;font-size:16px;font-family:monospace">{api_key}</code>
            </div>
            <p style="color:#666;font-size:15px">
                <strong>Get started:</strong><br>
                • <a href="https://app.dejaview.io">Open the web app</a> and enter your key<br>
                • API endpoint: <code>https://api.dejaview.io</code><br>
                • Docs: <a href="https://api.dejaview.io/docs">api.dejaview.io/docs</a>
            </p>
            <p style="color:#666;font-size:15px"><strong>Quick start:</strong></p>
            <pre style="background:#f5f5f5;padding:16px;border-radius:8px;font-size:13px">curl -X POST https://api.dejaview.io/v1/facts \
  -H "Authorization: Bearer {api_key}" \
  -H "Content-Type: application/json" \
  -d '{{"facts":[{{"subject":"Me","predicate":"working_on","object":"My Project"}}]}}' </pre>
            <p style="color:#aaa;font-size:13px;margin-top:32px">
                Questions? Reply to this email.<br>
                — Jake & the DejaView team
            </p>
        </div>
        """
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.load(resp)
            print(f"✅ Welcome email sent to {email}: {result.get('id')}")
    except Exception as e:
        print(f"❌ Email failed: {e}")


# ============ LemonSqueezy Webhook ============

import hashlib, hmac

@app.post("/webhooks/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    """Handle LemonSqueezy payment webhooks."""
    import os, json
    secret = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")

    payload = await request.body()
    sig = request.headers.get("x-signature", "")

    # Verify signature
    if secret:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event = json.loads(payload)
    event_name = event.get("meta", {}).get("event_name", "")
    data = event.get("data", {})
    attrs = data.get("attributes", {})

    print(f"📦 LemonSqueezy event: {event_name}")

    if event_name in ("order_created", "subscription_created"):
        email = (
            attrs.get("user_email") or
            attrs.get("customer_email") or
            event.get("meta", {}).get("custom_data", {}).get("email", "")
        )
        if not email:
            return {"status": "skipped", "reason": "no email found"}

        # Create user + generate API key
        user = _create_user(email=email, tier="pro", source="lemonsqueezy")
        print(f"✅ Created user: {email} -> {user['api_key']}")

        # Send welcome email
        _send_welcome_email(email, user["api_key"])

        return {"status": "ok", "user_created": email}

    return {"status": "ok", "event": event_name, "action": "ignored"}
