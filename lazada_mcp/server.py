#!/usr/bin/env python3
"""
Lazada MCP Server
Exposes Lazada Open Platform (seller) tools + public scraper tools
for lazada.com.ph

Transport modes:
  stdio  — default, for local use (Claude Desktop on same machine)
  sse    — HTTP/SSE server for remote use (Claude Desktop on a different machine)

Usage:
  python server.py              # stdio (local)
  python server.py --sse        # SSE on port 8000
  python server.py --sse --port 9000  # SSE on custom port

Environment variables:
  LAZADA_APP_KEY        required for seller tools
  LAZADA_APP_SECRET     required for seller tools
  LAZADA_ACCESS_TOKEN   required for seller tools (from OAuth)
  MCP_PORT              SSE port override (default: 8000)
"""
import argparse
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from lazada_api import LazadaClient, LazadaAPIError
from lazada_scraper import search_products, get_product_detail

# ── Init ──────────────────────────────────────────────────────────────────────

app = Server("lazada-mcp")

def _get_client() -> LazadaClient:
    """Build LazadaClient from env vars. Raises if not configured."""
    app_key = os.environ.get("LAZADA_APP_KEY")
    app_secret = os.environ.get("LAZADA_APP_SECRET")
    access_token = os.environ.get("LAZADA_ACCESS_TOKEN")
    if not app_key or not app_secret:
        raise EnvironmentError(
            "LAZADA_APP_KEY and LAZADA_APP_SECRET must be set to use seller tools."
        )
    return LazadaClient(app_key, app_secret, access_token)


def _ok(data: Any) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, indent=2))])


def _err(msg: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=f"Error: {msg}")],
        isError=True,
    )


# ── Tool definitions ───────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Public / Scraper ──────────────────────────────────────────────
        Tool(
            name="lazada_search_products",
            description=(
                "Search for products on Lazada Philippines (lazada.com.ph) by keyword. "
                "Returns public product listings including name, price, rating, and URL. "
                "No seller credentials required."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search keyword, e.g. 'laptop', 'running shoes'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max products to return (1–20). Default: 10.",
                        "default": 10,
                    },
                },
                "required": ["keyword"],
            },
        ),
        Tool(
            name="lazada_get_product_detail",
            description=(
                "Get full details of a specific Lazada Philippines product page: "
                "title, price, brand, rating, description, images. "
                "Pass the full lazada.com.ph product URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full Lazada product URL, e.g. https://www.lazada.com.ph/products/...",
                    },
                },
                "required": ["url"],
            },
        ),
        # ── Seller — Products ─────────────────────────────────────────────
        Tool(
            name="lazada_get_my_products",
            description=(
                "Get your own Lazada seller product listings. "
                "Requires seller credentials (LAZADA_APP_KEY, LAZADA_APP_SECRET, LAZADA_ACCESS_TOKEN)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter by status: all | live | inactive | deleted | pending | rejected | sold-out",
                        "default": "all",
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional search string to filter by product name or SKU.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max products to return (1–500). Default: 20.",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset. Default: 0.",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="lazada_update_price_quantity",
            description=(
                "Update the price and/or stock quantity of a seller SKU on Lazada. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "seller_sku": {
                        "type": "string",
                        "description": "Your Seller SKU identifier.",
                    },
                    "price": {
                        "type": "number",
                        "description": "New price in PHP.",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "New stock quantity.",
                    },
                },
                "required": ["seller_sku", "price", "quantity"],
            },
        ),
        # ── Seller — Orders ────────────────────────────────────────────────
        Tool(
            name="lazada_get_orders",
            description=(
                "Get your Lazada seller orders, optionally filtered by status or date. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": (
                            "Filter by order status: unpaid | pending | ready_to_ship | "
                            "delivered | returned | shipped | failed | canceled"
                        ),
                    },
                    "created_after": {
                        "type": "string",
                        "description": "ISO8601 datetime, e.g. '2024-01-01T00:00:00+08:00'. Returns orders after this date.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max orders to return. Default: 20.",
                        "default": 20,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset. Default: 0.",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="lazada_get_order_detail",
            description=(
                "Get details and items for a specific Lazada order by order ID. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "The Lazada order ID.",
                    },
                },
                "required": ["order_id"],
            },
        ),
        # ── Seller — Catalog ──────────────────────────────────────────────
        Tool(
            name="lazada_get_category_tree",
            description=(
                "Get the full Lazada Philippines product category tree. "
                "Useful for finding category IDs when creating or updating products. "
                "Requires seller credentials."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="lazada_get_brands",
            description=(
                "Search for brands on Lazada Philippines. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Brand name to search for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default: 50.",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
        # ── Seller — Auth ──────────────────────────────────────────────────
        Tool(
            name="lazada_get_seller_info",
            description=(
                "Get info about the currently authenticated seller account. "
                "Requires seller credentials."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="lazada_refresh_token",
            description=(
                "Refresh the seller access token using a refresh token. "
                "Returns a new access_token and refresh_token."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "refresh_token": {
                        "type": "string",
                        "description": "The refresh token from a previous OAuth flow.",
                    },
                },
                "required": ["refresh_token"],
            },
        ),
    ]


# ── Tool handlers ──────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:

    # ── Public / Scraper tools ──────────────────────────────────────────────
    if name == "lazada_search_products":
        try:
            keyword = arguments["keyword"]
            limit = min(int(arguments.get("limit", 10)), 20)
            results = search_products(keyword, limit)
            return _ok({"keyword": keyword, "count": len(results), "products": results})
        except Exception as e:
            return _err(f"Scraper error: {e}")

    if name == "lazada_get_product_detail":
        try:
            url = arguments["url"]
            detail = get_product_detail(url)
            return _ok(detail)
        except Exception as e:
            return _err(f"Scraper error: {e}")

    # ── Seller tools ────────────────────────────────────────────────────────
    try:
        client = _get_client()
    except EnvironmentError as e:
        return _err(str(e))

    try:
        if name == "lazada_get_my_products":
            data = client.get_products(
                filter=arguments.get("filter", "all"),
                search=arguments.get("search"),
                limit=int(arguments.get("limit", 20)),
                offset=int(arguments.get("offset", 0)),
            )
            return _ok(data)

        elif name == "lazada_update_price_quantity":
            data = client.update_price_quantity(
                seller_sku=arguments["seller_sku"],
                price=float(arguments["price"]),
                quantity=int(arguments["quantity"]),
            )
            return _ok(data)

        elif name == "lazada_get_orders":
            data = client.get_orders(
                status=arguments.get("status"),
                created_after=arguments.get("created_after"),
                limit=int(arguments.get("limit", 20)),
                offset=int(arguments.get("offset", 0)),
            )
            return _ok(data)

        elif name == "lazada_get_order_detail":
            order_id = int(arguments["order_id"])
            orders = client.get_order(order_id)
            items = client.get_order_items(order_id)
            return _ok({"order": orders, "items": items})

        elif name == "lazada_get_category_tree":
            data = client.get_category_tree()
            return _ok(data)

        elif name == "lazada_get_brands":
            data = client.get_brands(
                keyword=arguments.get("keyword"),
                limit=int(arguments.get("limit", 50)),
            )
            return _ok(data)

        elif name == "lazada_get_seller_info":
            data = client.get_seller()
            return _ok(data)

        elif name == "lazada_refresh_token":
            data = client.refresh_access_token(arguments["refresh_token"])
            return _ok(data)

        else:
            return _err(f"Unknown tool: {name}")

    except LazadaAPIError as e:
        return _err(f"Lazada API error {e.code}: {e.message}")
    except Exception as e:
        return _err(str(e))
    finally:
        client.close()


# ── Entry point ────────────────────────────────────────────────────────────────

async def _run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def _run_sse(host: str, port: int):
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.routing import Mount, Route
    import uvicorn

    sse_transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    class NoCacheMiddleware(BaseHTTPMiddleware):
        """Prevent Cloudflare and proxies from buffering SSE responses."""
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            if "text/event-stream" in response.headers.get("content-type", ""):
                response.headers["Cache-Control"] = "no-cache"
                response.headers["X-Accel-Buffering"] = "no"
            return response

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ]
    )
    starlette_app.add_middleware(NoCacheMiddleware)

    print(f"Lazada MCP running on http://{host}:{port}/sse")
    uvicorn.run(starlette_app, host=host, port=port)


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Lazada MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run as SSE HTTP server (for remote connections)")
    parser.add_argument("--host", default="0.0.0.0", help="SSE bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", 8000)), help="SSE port (default: 8000)")
    args = parser.parse_args()

    if args.sse:
        _run_sse(args.host, args.port)
    else:
        asyncio.run(_run_stdio())
