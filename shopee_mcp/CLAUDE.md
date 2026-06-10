# Shopee MCP — Project Context for Claude Code

## What this is
A Python MCP server for Shopee Philippines. Exposes 9 tools to any MCP-compatible AI platform (Claude Desktop, Claude Code, etc.).

## Two distinct layers
1. **Public scraper** (`shopee_scraper.py`) — uses Playwright (headless Chromium) to get session cookies, then calls Shopee's internal JSON search/item API. No seller credentials needed.
2. **Seller API** (`shopee_api.py`) — wraps the official Shopee Open Platform API v2. Requires seller credentials.

## Entry point
`server.py` — supports two transport modes:
```bash
python server.py              # stdio (local)
python server.py --sse        # SSE HTTP server on port 7772 (remote)
```

## Deployment
Docker for remote/production. Default port is **7772** (different from lazada_mcp's 7771).
```bash
docker compose up -d --build
```
After redeploying, restart Claude Desktop and start a new Claude Code session.

## Setup steps
1. `pip install -r requirements.txt`
2. `playwright install chromium && playwright install-deps chromium`
3. Test public tools immediately — no credentials needed
4. For seller tools: register at open.shopee.com, complete OAuth flow

## Environment variables (seller tools only)
```
SHOPEE_PARTNER_ID      numeric partner ID
SHOPEE_PARTNER_KEY     live key from open.shopee.com
SHOPEE_ACCESS_TOKEN    OAuth access token
SHOPEE_SHOP_ID         numeric shop ID
```

## Key files
| File | Purpose |
|---|---|
| `server.py` | MCP entry point — stdio and SSE transport, all tool definitions |
| `shopee_api.py` | Shopee Open Platform v2 wrapper — HMAC-SHA256 signed requests |
| `shopee_scraper.py` | Playwright scraper — homepage cookies → internal JSON API |
| `Dockerfile` | Docker image using `mcr.microsoft.com/playwright/python` base |
| `requirements.txt` | `mcp`, `httpx`, `playwright`, `uvicorn`, `starlette` |

## How the scraper works
Shopee's frontend calls these internal endpoints:
- Search: `https://shopee.ph/api/v4/search/search_items?keyword=...`
- Detail: `https://shopee.ph/api/v4/item/get?itemid=...&shopid=...`

Playwright visits the homepage first to acquire session cookies, then hits the JSON endpoints. Prices are returned as integers × 100000 (e.g., 199900000 = ₱1,999.00).

## Shopee API v2 signing
Different from Lazada. Base string:
- Shop-level: `partner_id + api_path + timestamp + access_token + shop_id`
- Non-auth: `partner_id + api_path + timestamp`
Signed with HMAC-SHA256 using `partner_key`.

## Important: Playwright + Docker version pinning
Same rule as lazada_mcp — if Playwright upgrades, update Dockerfile base image to match:
`mcr.microsoft.com/playwright/python:v{version}-jammy`

## What's NOT here yet
- OAuth redirect handler (manual step — see README)
- Unit tests
- Proxy support (may be needed if Shopee bot detection tightens)
- Error retry logic
