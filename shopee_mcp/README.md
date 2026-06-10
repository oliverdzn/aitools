# Shopee MCP Server

MCP server for Shopee Philippines (`shopee.ph`) with two categories of tools:

- **Public tools** — search and browse Shopee marketplace products using Playwright (headless Chromium). No credentials needed.
- **Seller tools** — manage your own listings, orders, pricing, and inventory via the official Shopee Open Platform API v2. Requires seller credentials.

---

## Requirements

- Python 3.11+
- Chromium (installed via Playwright)
- A Shopee seller account + registered app on open.shopee.com (for seller tools only)

---

## Installation (local)

```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

---

## Running the server

### Local (stdio)
```bash
python server.py
```

### Remote (SSE)
```bash
python server.py --sse --port 7772
```

### Docker (recommended for remote/production)
```bash
docker build -t shopee-mcp .
docker run -d -p 7772:7772 \
  -e SHOPEE_PARTNER_ID=your_partner_id \
  -e SHOPEE_PARTNER_KEY=your_partner_key \
  -e SHOPEE_ACCESS_TOKEN=your_access_token \
  -e SHOPEE_SHOP_ID=your_shop_id \
  --name shopee-mcp shopee-mcp
```

Or with docker-compose:
```yaml
services:
  shopee-mcp:
    build: .
    ports:
      - "7772:7772"
    environment:
      - SHOPEE_PARTNER_ID=your_partner_id
      - SHOPEE_PARTNER_KEY=your_partner_key
      - SHOPEE_ACCESS_TOKEN=your_access_token
      - SHOPEE_SHOP_ID=your_shop_id
    restart: unless-stopped
```

---

## Getting Shopee Seller Credentials

1. Go to [open.shopee.com](https://open.shopee.com) and sign in with your Shopee seller account
2. Click **Add New App** → select category **Seller In House System** → submit
3. Click **Go-Live** to get your production `Partner ID` and `Partner Key`
4. Get an Access Token via the OAuth flow:

```
# Step 1 — Generate authorization URL:
https://partner.shopeemobile.com/api/v2/shop/auth_partner
  ?partner_id=YOUR_PARTNER_ID
  &timestamp=UNIX_TIMESTAMP
  &sign=SHA256(partner_id + /api/v2/shop/auth_partner + timestamp)
  &redirect=YOUR_REDIRECT_URI

# Step 2 — Seller authorizes in browser, you receive code + shop_id in redirect

# Step 3 — Exchange code for tokens:
python3 -c "
from shopee_api import ShopeeClient
client = ShopeeClient(PARTNER_ID, 'PARTNER_KEY', '', SHOP_ID)
# POST to /auth/token/get with the code
"
```

**Token expiry**: Access tokens expire after 4 hours. Use `shopee_refresh_token` to renew.

---

## Connecting to Claude Desktop

Add to `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Remote (SSE)
```json
{
  "mcpServers": {
    "shopee": {
      "url": "https://your-server.example.com/sse"
    }
  }
}
```

### Local (stdio)
```json
{
  "mcpServers": {
    "shopee": {
      "command": "python",
      "args": ["/absolute/path/to/shopee_mcp/server.py"],
      "env": {
        "SHOPEE_PARTNER_ID": "your_partner_id",
        "SHOPEE_PARTNER_KEY": "your_partner_key",
        "SHOPEE_ACCESS_TOKEN": "your_access_token",
        "SHOPEE_SHOP_ID": "your_shop_id"
      }
    }
  }
}
```

> **Note:** After redeploying the Docker container, restart Claude Desktop and start a new Claude Code session.

---

## Available Tools

### Public — no credentials needed

| Tool | Description |
|---|---|
| `shopee_search_products` | Search shopee.ph by keyword. Returns name, price, rating, sold count, seller, URL. |
| `shopee_get_product_detail` | Full product details by item_id + shop_id: title, price, description, stock, images. |

### Seller — requires credentials

| Tool | Description |
|---|---|
| `shopee_get_shop_info` | Get your Shopee seller shop info |
| `shopee_get_my_products` | List your product listings (filter by status) |
| `shopee_update_price` | Update price for a product model |
| `shopee_update_stock` | Update stock quantity for a product model |
| `shopee_get_orders` | List orders filtered by status or date range |
| `shopee_get_order_detail` | Full details for one or more orders by SN |
| `shopee_refresh_token` | Refresh an expired access token |

---

## Example prompts

```
Search Shopee for wireless earphones under ₱500
```
```
Show me my Shopee orders from the last 7 days
```
```
Update the price of item 123456789 to ₱999
```
```
What are my active Shopee product listings?
```
```
Get details for Shopee item 123456789 from shop 987654321
```

---

## How the scraper works

`shopee_scraper.py` uses Playwright to visit `shopee.ph` and acquire session cookies, then calls Shopee's internal JSON API:

- **Search**: `https://shopee.ph/api/v4/search/search_items?keyword=...`
- **Detail**: `https://shopee.ph/api/v4/item/get?itemid=...&shopid=...`

Prices in Shopee's API are integers × 100,000 (e.g., `199900000` = ₱1,999.00). The scraper converts these automatically.

---

## File structure

```
shopee_mcp/
├── server.py           # MCP server entry point (stdio + SSE)
├── shopee_api.py       # Shopee Open Platform v2 wrapper (seller tools)
├── shopee_scraper.py   # Playwright scraper (public tools)
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Troubleshooting

**Seller tools return credential error**
→ Set all four env vars: `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_ACCESS_TOKEN`, `SHOPEE_SHOP_ID`.

**Search returns empty or bot-detection error**
→ Shopee has stronger bot detection than Lazada. Try again — occasional failures are normal. For sustained use, consider adding residential proxy support.

**Access token expired**
→ Shopee tokens expire after 4 hours. Use `shopee_refresh_token` to renew.

**Playwright version mismatch**
→ Update Dockerfile base image to match installed Playwright version: `mcr.microsoft.com/playwright/python:vX.XX.X-jammy`.

**Tools not appearing after redeploy**
→ Restart Claude Desktop and start a new Claude Code session.
