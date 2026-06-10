# Lazada MCP Server

MCP server for Lazada Philippines (`lazada.com.ph`) with two categories of tools:

- **Public tools** — search and browse Lazada marketplace products. Uses Lazada's internal JSON API directly via `httpx`. No credentials, no Chromium, no cost.
- **Seller tools** — manage your own listings, orders, pricing, and inventory via the official Lazada Open Platform API. Requires seller credentials.

---

## Requirements

- Python 3.11+
- A Lazada seller account + registered app (for seller tools only)

---

## Installation

```bash
# 1. Clone / navigate to this folder
cd "Lazada MCP"

# 2. Install dependencies
pip install -r requirements.txt
```

That's it. No browser installation needed.

---

## Configuration

### Public tools (no setup needed)
`lazada_search_products` and `lazada_get_product_detail` work immediately with no credentials.

### Seller tools
Requires three environment variables:

| Variable | Description |
|---|---|
| `LAZADA_APP_KEY` | Your app's key from open.lazada.com |
| `LAZADA_APP_SECRET` | Your app's secret from open.lazada.com |
| `LAZADA_ACCESS_TOKEN` | OAuth access token (see Getting Credentials below) |

---

## Getting Lazada Seller Credentials

1. Go to [open.lazada.com](https://open.lazada.com) and sign in with your Lazada seller account
2. Click **Create App** → fill in app name and description → submit
3. Copy your **App Key** and **App Secret**
4. Get an Access Token via the OAuth flow:

```
# Step 1 — Send seller to this URL in their browser:
https://auth.lazada.com/oauth/authorize?response_type=code&force_auth=true&redirect_uri=YOUR_REDIRECT_URI&client_id=YOUR_APP_KEY

# Step 2 — After they authorize, you receive an auth_code in the redirect URL

# Step 3 — Exchange auth_code for tokens:
python3 -c "
from lazada_api import LazadaClient
client = LazadaClient('YOUR_APP_KEY', 'YOUR_APP_SECRET')
tokens = client.generate_access_token('YOUR_AUTH_CODE')
print(tokens)
"
# Save the access_token and refresh_token from the output
```

**Token expiry**: Access tokens expire after 30 days. Use the `lazada_refresh_token` MCP tool or call `client.refresh_access_token(refresh_token)` to renew.

---

## Connecting to Claude Desktop

Add to `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lazada": {
      "command": "python",
      "args": ["C:/Users/beron/Claude/Projects/Lazada MCP/server.py"],
      "env": {
        "LAZADA_APP_KEY": "your_app_key",
        "LAZADA_APP_SECRET": "your_app_secret",
        "LAZADA_ACCESS_TOKEN": "your_access_token"
      }
    }
  }
}
```

Restart Claude Desktop — the Lazada tools will appear automatically.

---

## Connecting to Claude Code

Add to your project's `.mcp.json` or to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "lazada": {
      "command": "python",
      "args": ["/absolute/path/to/Lazada MCP/server.py"],
      "env": {
        "LAZADA_APP_KEY": "your_app_key",
        "LAZADA_APP_SECRET": "your_app_secret",
        "LAZADA_ACCESS_TOKEN": "your_access_token"
      }
    }
  }
}
```

Or run inline:
```bash
LAZADA_APP_KEY=xxx LAZADA_APP_SECRET=yyy LAZADA_ACCESS_TOKEN=zzz python server.py
```

---

## Available Tools

### Public — no credentials needed

| Tool | Description |
|---|---|
| `lazada_search_products` | Search lazada.com.ph by keyword. Returns name, price, rating, seller, URL. |
| `lazada_get_product_detail` | Full product details from a product URL: title, price, brand, rating, stock, images. |

### Seller — requires credentials

| Tool | Description |
|---|---|
| `lazada_get_my_products` | List your seller product listings (filter by status, search by name/SKU) |
| `lazada_update_price_quantity` | Update price and/or stock quantity for a SKU |
| `lazada_get_orders` | List orders, optionally filtered by status or date |
| `lazada_get_order_detail` | Full detail + line items for a specific order |
| `lazada_get_category_tree` | Full Lazada PH category tree (for creating/updating products) |
| `lazada_get_brands` | Search brands by keyword |
| `lazada_get_seller_info` | Your seller account info |
| `lazada_refresh_token` | Refresh an expired access token |

---

## Example prompts

```
Search Lazada for tuya smart bulbs under ₱500
```
```
Show me all my pending orders from this week
```
```
Update the price of SKU ABC-123 to ₱799 and set stock to 50
```
```
What are my top 10 active product listings?
```
```
Get full details on this Lazada product: https://www.lazada.com.ph/products/...
```

---

## How the scraper works

`lazada_scraper.py` calls Lazada's internal search API directly:

```
GET https://www.lazada.com.ph/catalog/?q=tuya+smart+bulb&ajax=true
```

Lazada's own website uses this same endpoint to load search results in the browser. The response is structured JSON — no HTML parsing, no Chromium. This is why no browser installation is needed and there's no per-request cost.

---

## File structure

```
Lazada MCP/
├── server.py           # MCP server entry point (stdio transport)
├── lazada_api.py       # Official LazOP API wrapper (seller tools)
├── lazada_scraper.py   # Direct HTTP scraper (public tools)
├── requirements.txt    # mcp, httpx
├── README.md           # This file
└── FEASIBILITY.md      # Research notes on API vs scraper approach
```

---

## Troubleshooting

**Seller tools return "LAZADA_APP_KEY must be set"**
→ You haven't set the env vars. Public tools still work without them.

**Search returns empty results**
→ Try a simpler keyword. Lazada occasionally returns 0 results for very specific queries.

**Access token expired error**
→ Use `lazada_refresh_token` with your refresh token to get a new one.

**Connection refused on Claude Desktop**
→ Make sure the `args` path uses the correct absolute path and Python is in your PATH.
