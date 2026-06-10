# Lazada MCP — Feasibility Report

## TL;DR

**Feasibility: High for seller-side data, Medium for public product browsing.**

Two distinct data access paths exist, each suitable for different MCP tools:

| Approach | What it covers | Auth required | Reliability |
|---|---|---|---|
| **Lazada Open Platform (official API)** | Your own products, orders, inventory, pricing | Yes — seller credentials + OAuth | High (official, stable) |
| **Web scraper** | Public product listings, prices, search results from lazada.com | No | Medium (bot detection risk) |

---

## 1. Lazada Open Platform API

### How it works

Lazada's official API uses signed HTTP requests (HMAC-SHA256). Every request requires:
- `AppKey` + `AppSecret` (from a registered developer app)
- `AccessToken` (OAuth 2.0 flow — the seller authorizes your app)
- `Timestamp` + `Signature` (computed from all params)

Base endpoint: `https://api.lazada.com/rest` (or country-specific variants like `api.lazada.sg`, `api.lazada.com.my`, etc.)

### Available product endpoints

| Endpoint | What it does |
|---|---|
| `GET /products/get` | List/search **your own** seller products |
| `POST /product/create` | Create a new product listing |
| `POST /product/update` | Update a product |
| `DELETE /product/remove` | Remove a product |
| `POST /product/price_quantity/update` | Update price + stock |
| `GET /products/brands/query` | Get brand list |
| `GET /category/tree/get` | Get category tree |
| `GET /category/attributes/get` | Get attributes for a category |

### Key limitation ⚠️

The official API is **seller-centric**. `GetProducts` only returns products belonging to the authenticated seller — **not all Lazada marketplace products**. There is no public product search API. This is ideal for:
- Managing your own store inventory
- Automating order workflows
- Bulk pricing or stock updates via AI

### Countries supported

Singapore, Malaysia, Thailand, Philippines, Vietnam, Indonesia

### Python SDK (official, from Lazada)

```python
import lazop

client = lazop.LazopClient('https://api.lazada.sg/rest', '<AppKey>', '<AppSecret>')
request = lazop.LazopRequest('/products/get')
request.add_api_param('filter', 'all')
request.add_api_param('limit', '20')
response = client.execute(request, '<AccessToken>')
print(response.body)
```

---

## 2. Web Scraper (Public Product Access)

### What it can get

- Product names, prices, ratings, review counts
- Product images and URLs
- Search results from keyword queries
- Category browsing

### How scrapers work on Lazada

Lazada is a JS-heavy SPA (Alibaba stack). Scraping requires:
- **Playwright or Selenium** to render JavaScript
- Stealth patches (hide `navigator.webdriver`, fake fingerprints)
- Proxy rotation for sustained scraping
- Rate limiting / delays to avoid blocks

### Feasibility assessment

| Factor | Assessment |
|---|---|
| JavaScript rendering needed | Yes — page is client-side rendered |
| Anti-bot protection | Moderate (Alibaba CDN, likely Akamai bot manager) |
| Stealth techniques effectiveness | Works for light/intermittent scraping |
| Sustained high-volume scraping | Risky — IP blocks, CAPTCHAs expected |
| Legal/ToS | Lazada ToS prohibits scraping; acceptable for personal/research use |

Existing open-source scrapers (CaesarNgyn, nabihahmohamad on GitHub) confirm basic scraping is achievable with Playwright/BeautifulSoup.

---

## 3. Recommended MCP Architecture

### Tools to expose

**Tier A — Official API (seller tools)**
```
search_my_products(filter, search_query, limit)
get_product_detail(seller_sku)
update_product_price(sku, price, special_price)
update_product_stock(sku, quantity)
get_orders(status, created_after, limit)
get_order_detail(order_id)
get_category_tree()
get_brands(keyword)
```

**Tier B — Scraper (public browsing tools)**
```
search_products(keyword, country, limit)
get_product_page(url)
```

### Tech stack recommendation

| Component | Choice | Reason |
|---|---|---|
| Language | Python | Official Lazada SDK is Python; `mcp` package is mature |
| MCP SDK | `mcp` (pip) | Official Anthropic MCP Python SDK |
| Scraping | Playwright + playwright-stealth | Best JS rendering + anti-bot evasion |
| Transport | stdio (local) or SSE/HTTP (remote) | stdio simplest for Claude Desktop |

### File structure

```
lazada-mcp/
├── server.py            # MCP server entrypoint
├── lazada_api.py        # Official API wrapper (LazOP)
├── lazada_scraper.py    # Playwright-based scraper
├── tools/
│   ├── products.py      # Product-related MCP tools
│   ├── orders.py        # Order-related MCP tools
│   └── scraper.py       # Public search MCP tools
├── config.py            # Credentials loader (env vars)
├── requirements.txt
└── README.md
```

### Environment variables required

```
LAZADA_APP_KEY=
LAZADA_APP_SECRET=
LAZADA_ACCESS_TOKEN=        # From OAuth flow
LAZADA_COUNTRY=sg           # sg | my | th | ph | vn | id
```

---

## 4. Open Questions Before Building

1. **Use case** — Is this for managing a seller store, or browsing marketplace products as a buyer?
2. **Do you have Lazada seller credentials?** Official API requires a registered seller app on open.lazada.com.
3. **Countries** — Which Lazada market(s) to target?
4. **Scraper scope** — Is public product search needed, or is the seller API sufficient?

---

## 5. Next Steps

1. Confirm use case (seller tools vs. public search vs. both)
2. Register app on [open.lazada.com](https://open.lazada.com) → get AppKey + AppSecret
3. Complete OAuth flow to get AccessToken
4. Build `server.py` with MCP tools wrapping `lazada_api.py`
5. Add scraper layer for public search if needed
6. Test with Claude Desktop via `claude_desktop_config.json`
