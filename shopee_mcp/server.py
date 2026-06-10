#!/usr/bin/env python3
"""
Shopee MCP Server
Exposes Shopee Open Platform (seller) tools + public scraper tools
for shopee.ph

Transport modes:
  stdio  — default, for local use (Claude Desktop on same machine)
  sse    — HTTP/SSE server for remote use (Claude Desktop on a different machine)

Usage:
  python server.py              # stdio (local)
  python server.py --sse        # SSE on port 7772
  python server.py --sse --port 9000  # SSE on custom port

Environment variables:
  SHOPEE_PARTNER_ID     required for seller tools (numeric)
  SHOPEE_PARTNER_KEY    required for seller tools
  SHOPEE_ACCESS_TOKEN   required for seller tools (from OAuth)
  SHOPEE_SHOP_ID        required for seller tools (numeric)
  MCP_PORT              SSE port override (default: 7772)
"""
import argparse
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

from shopee_api import ShopeeClient, ShopeeAPIError
from shopee_scraper import search_products, get_product_detail

app = Server("shopee-mcp")


def _get_client() -> ShopeeClient:
    partner_id = os.environ.get("SHOPEE_PARTNER_ID")
    partner_key = os.environ.get("SHOPEE_PARTNER_KEY")
    access_token = os.environ.get("SHOPEE_ACCESS_TOKEN")
    shop_id = os.environ.get("SHOPEE_SHOP_ID")
    if not partner_id or not partner_key or not shop_id:
        raise EnvironmentError(
            "SHOPEE_PARTNER_ID, SHOPEE_PARTNER_KEY, and SHOPEE_SHOP_ID must be set to use seller tools."
        )
    return ShopeeClient(int(partner_id), partner_key, access_token or "", int(shop_id))


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
            name="shopee_search_products",
            description=(
                "Search for products on Shopee Philippines (shopee.ph) by keyword. "
                "Returns public listings including name, price, rating, sold count, and URL. "
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
                        "description": "Max products to return (1–60). Default: 10.",
                        "default": 10,
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort order: sales | price_asc | price_desc | newest | relevance. Default: sales.",
                        "default": "sales",
                    },
                },
                "required": ["keyword"],
            },
        ),
        Tool(
            name="shopee_get_product_detail",
            description=(
                "Get full details of a specific Shopee Philippines product: "
                "title, price, description, rating, stock, images. "
                "Requires item_id and shop_id (available from shopee_search_products results)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "Shopee item ID (from search results).",
                    },
                    "shop_id": {
                        "type": "integer",
                        "description": "Shopee shop ID (from search results).",
                    },
                },
                "required": ["item_id", "shop_id"],
            },
        ),
        # ── Seller — Shop ─────────────────────────────────────────────────
        Tool(
            name="shopee_get_shop_info",
            description=(
                "Get info about the currently authenticated Shopee seller shop. "
                "Requires seller credentials."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # ── Seller — Products ─────────────────────────────────────────────
        Tool(
            name="shopee_get_my_products",
            description=(
                "List your Shopee seller product listings. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_status": {
                        "type": "string",
                        "description": "Filter by status: NORMAL | BANNED | DELETED | UNLIST. Default: NORMAL.",
                        "default": "NORMAL",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max products to return (1–100). Default: 20.",
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
            name="shopee_update_price",
            description=(
                "Update the price of a Shopee seller product model. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "Shopee item ID.",
                    },
                    "model_id": {
                        "type": "integer",
                        "description": "Model ID (0 for single-variant items).",
                        "default": 0,
                    },
                    "price": {
                        "type": "number",
                        "description": "New price in PHP.",
                    },
                },
                "required": ["item_id", "price"],
            },
        ),
        Tool(
            name="shopee_update_stock",
            description=(
                "Update the stock quantity of a Shopee seller product model. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "Shopee item ID.",
                    },
                    "model_id": {
                        "type": "integer",
                        "description": "Model ID (0 for single-variant items).",
                        "default": 0,
                    },
                    "stock": {
                        "type": "integer",
                        "description": "New stock quantity.",
                    },
                },
                "required": ["item_id", "stock"],
            },
        ),
        # ── Seller — Orders ────────────────────────────────────────────────
        Tool(
            name="shopee_get_orders",
            description=(
                "Get your Shopee seller orders, optionally filtered by status or date range. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "order_status": {
                        "type": "string",
                        "description": (
                            "Filter by status: UNPAID | READY_TO_SHIP | PROCESSED | SHIPPED | "
                            "COMPLETED | IN_CANCEL | CANCELLED | TO_RETURN"
                        ),
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Fetch orders from the last N days. Default: 30.",
                        "default": 30,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max orders to return (1–100). Default: 20.",
                        "default": 20,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="shopee_get_order_detail",
            description=(
                "Get full details for one or more Shopee orders by order SN. "
                "Requires seller credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "order_sn_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of order serial numbers (max 50).",
                    },
                },
                "required": ["order_sn_list"],
            },
        ),
        # ── Seller — Auth ──────────────────────────────────────────────────
        Tool(
            name="shopee_refresh_token",
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
    if name == "shopee_search_products":
        try:
            keyword = arguments["keyword"]
            limit = min(int(arguments.get("limit", 10)), 60)
            sort_by = arguments.get("sort_by", "sales")
            results = search_products(keyword, limit, sort_by)
            return _ok({"keyword": keyword, "count": len(results), "products": results})
        except Exception as e:
            return _err(f"Scraper error: {e}")

    if name == "shopee_get_product_detail":
        try:
            item_id = int(arguments["item_id"])
            shop_id = int(arguments["shop_id"])
            detail = get_product_detail(item_id, shop_id)
            return _ok(detail)
        except Exception as e:
            return _err(f"Scraper error: {e}")

    # ── Seller tools ────────────────────────────────────────────────────────
    try:
        client = _get_client()
    except EnvironmentError as e:
        return _err(str(e))

    try:
        if name == "shopee_get_shop_info":
            return _ok(client.get_shop_info())

        elif name == "shopee_get_my_products":
            data = client.get_item_list(
                offset=int(arguments.get("offset", 0)),
                limit=int(arguments.get("limit", 20)),
                item_status=arguments.get("item_status", "NORMAL"),
            )
            return _ok(data)

        elif name == "shopee_update_price":
            return _ok(client.update_price(
                item_id=int(arguments["item_id"]),
                model_id=int(arguments.get("model_id", 0)),
                original_price=float(arguments["price"]),
            ))

        elif name == "shopee_update_stock":
            return _ok(client.update_stock(
                item_id=int(arguments["item_id"]),
                model_id=int(arguments.get("model_id", 0)),
                normal_stock=int(arguments["stock"]),
            ))

        elif name == "shopee_get_orders":
            import time
            days = int(arguments.get("days_back", 30))
            now = int(time.time())
            return _ok(client.get_order_list(
                time_from=now - days * 86400,
                time_to=now,
                order_status=arguments.get("order_status"),
                page_size=int(arguments.get("limit", 20)),
            ))

        elif name == "shopee_get_order_detail":
            order_sn_list = arguments["order_sn_list"][:50]
            return _ok(client.get_order_detail(order_sn_list))

        elif name == "shopee_refresh_token":
            return _ok(client.refresh_access_token(arguments["refresh_token"]))

        else:
            return _err(f"Unknown tool: {name}")

    except ShopeeAPIError as e:
        return _err(f"Shopee API error {e.error}: {e.message}")
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

    print(f"Shopee MCP running on http://{host}:{port}/sse")
    uvicorn.run(starlette_app, host=host, port=port)


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Shopee MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run as SSE HTTP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", 7772)))
    args = parser.parse_args()

    if args.sse:
        _run_sse(args.host, args.port)
    else:
        asyncio.run(_run_stdio())
