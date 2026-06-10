# Lazada MCP — Project Context for Claude Code

## What this is
A Python MCP server for Lazada Philippines. Exposes 10 tools to any MCP-compatible AI platform (Claude Desktop, Claude Code, etc.).

## Two distinct layers
1. **Public scraper** (`lazada_scraper.py`) — uses Playwright (headless Chromium) to bypass Lazada's bot detection, then calls Lazada's internal JSON search API. No seller credentials needed.
2. **Seller API** (`lazada_api.py`) — wraps the official Lazada Open Platform (LazOP). Requires seller credentials.

## Entry point
`server.py` — supports two transport modes:
```bash
python server.py              # stdio (local, for Claude Desktop on same machine)
python server.py --sse        # SSE HTTP server on port 8000 (remote)
python server.py --sse --port 7771  # custom port
```

## Deployment
Docker is used for remote/production deployment:
```bash
docker compose up -d --build
```
The container exposes port `7771` and runs `--sse` mode by default.

After redeploying, Claude Desktop must be restarted and a new Claude Code session must be started — SSE session IDs change on container restart.

## Setup steps (do these in order)
1. `pip install -r requirements.txt`
2. `playwright install chromium && playwright install-deps chromium`
3. Test public tools immediately — no credentials needed
4. For seller tools: get credentials from open.lazada.com (see README.md)

## Environment variables (seller tools only)
```
LAZADA_APP_KEY
LAZADA_APP_SECRET
LAZADA_ACCESS_TOKEN
```

## Key files
| File | Purpose |
|---|---|
| `server.py` | MCP entry point — stdio and SSE transport, all tool definitions and handlers |
| `lazada_api.py` | LazOP API wrapper — HMAC-SHA256 signed requests to api.lazada.com.ph |
| `lazada_scraper.py` | Playwright scraper — visits lazada.com.ph homepage, then calls catalog JSON API |
| `Dockerfile` | Docker image — uses `mcr.microsoft.com/playwright/python` base image |
| `requirements.txt` | `mcp`, `httpx[socks]`, `playwright`, `uvicorn`, `starlette` |

## How the scraper works
`lazada_scraper.py` launches headless Chromium via Playwright with stealth patches. It visits the Lazada homepage first (to get session cookies), then loads:
```
https://www.lazada.com.ph/catalog/?q={keyword}&ajax=true&sort={sort}
```
Products are in `response["mods"]["listItems"]`.
Playwright is required — plain httpx requests are blocked by Lazada's bot detection.

## Important: Playwright + Docker version pinning
The Dockerfile base image must match the installed Playwright version:
- `requirements.txt` pins `playwright>=1.44.0` (resolves to latest, currently 1.60.0)
- `Dockerfile` must use the matching image: `mcr.microsoft.com/playwright/python:v1.60.0-jammy`
- If Playwright upgrades, update both files together.

## Target market
Philippines only (`lazada.com.ph`, API endpoint `api.lazada.com.ph`).

## What's NOT here yet
- OAuth redirect handler (to get initial access token — manual step, see README)
- Unit tests
- Error retry logic

## Dependencies
- `mcp` — Anthropic MCP Python SDK
- `httpx[socks]` — HTTP client for the seller API
- `playwright` — headless Chromium for the public scraper
- `uvicorn` + `starlette` — SSE HTTP server for remote mode
