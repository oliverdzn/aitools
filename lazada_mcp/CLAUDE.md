# Lazada MCP — Project Context for Claude Code

## What this is
A Python MCP server for Lazada Philippines. Exposes 10 tools to any MCP-compatible AI platform (Claude Desktop, Claude Code, etc.).

## Two distinct layers
1. **Public scraper** (`lazada_scraper.py`) — hits Lazada's internal JSON API via httpx. No credentials, no cost, no Chromium.
2. **Seller API** (`lazada_api.py`) — wraps the official Lazada Open Platform (LazOP). Requires seller credentials.

## Entry point
`server.py` — stdio MCP server. Run with:
```bash
python server.py
```

## Setup steps (do these in order)
1. `pip install -r requirements.txt`
2. Test public tools immediately — no credentials needed
3. For seller tools: get credentials from open.lazada.com (see README.md)

## Environment variables (seller tools only)
```
LAZADA_APP_KEY
LAZADA_APP_SECRET
LAZADA_ACCESS_TOKEN
```

## Key files
| File | Purpose |
|---|---|
| `server.py` | MCP entry point, all tool definitions and handlers |
| `lazada_api.py` | LazOP API wrapper — HMAC-SHA256 signed requests to api.lazada.com.ph |
| `lazada_scraper.py` | httpx scraper — calls lazada.com.ph/catalog/?q=...&ajax=true |
| `requirements.txt` | `mcp`, `httpx[socks]` |

## How the scraper works
Lazada returns JSON from `https://www.lazada.com.ph/catalog/?q={keyword}&ajax=true`.
Products are in `response["mods"]["listItems"]`.
No Playwright, no Chromium needed.

## Target market
Philippines only (`lazada.com.ph`, API endpoint `api.lazada.com.ph`).

## What's NOT here yet
- OAuth redirect handler (to get initial access token — manual step, see README)
- Unit tests
- Error retry logic

## Dependencies
- `mcp` — Anthropic MCP Python SDK
- `httpx[socks]` — HTTP client for both scraper and API
