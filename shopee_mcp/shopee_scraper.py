"""
Shopee public product scraper for shopee.ph
Uses Playwright (headless Chromium) to bypass Shopee's bot detection,
then calls Shopee's internal search/item JSON API.
"""
import asyncio
import json
import os
import re
from typing import Any

from playwright.async_api import async_playwright

BASE = "https://shopee.ph"
SEARCH_URL = BASE + "/api/v4/search/search_items"
ITEM_URL = BASE + "/api/v4/item/get"

SESSION_FILE = os.environ.get("SHOPEE_SESSION_FILE", "/app/shopee_session.json")

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-PH', 'en'] });
window.chrome = { runtime: {} };
"""


def _parse_price(val: Any) -> float | None:
    if val is None:
        return None
    # Shopee returns prices in integer cents (multiply by 100000 for PHP display)
    if isinstance(val, (int, float)):
        return round(float(val) / 100000, 2)
    cleaned = re.sub(r"[^\d.]", "", str(val))
    return float(cleaned) if cleaned else None


async def _new_context(pw):
    browser = await pw.chromium.launch(headless=True)
    kwargs: dict = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "locale": "en-PH",
        "timezone_id": "Asia/Manila",
        "viewport": {"width": 1280, "height": 800},
    }
    if os.path.exists(SESSION_FILE):
        kwargs["storage_state"] = SESSION_FILE
    context = await browser.new_context(**kwargs)
    await context.add_init_script(_STEALTH_SCRIPT)
    return browser, context


async def _search(keyword: str, limit: int = 10, sort_by: str = "sales") -> list[dict]:
    sort_map = {"sales": "sales", "price_asc": "price", "price_desc": "price", "newest": "ctime", "relevance": "relevancy"}
    sort_param = sort_map.get(sort_by, "sales")
    order = "asc" if sort_by == "price_asc" else "desc"

    search_page_url = (
        f"{BASE}/search?keyword={keyword.replace(' ', '%20')}"
        f"&sortBy={sort_param}&order={order}"
    )

    captured: dict | None = None

    async with async_playwright() as pw:
        browser, context = await _new_context(pw)
        page = await context.new_page()

        async def on_response(resp):
            nonlocal captured
            if "api/v4/search/search_items" in resp.url and captured is None:
                try:
                    captured = await resp.json()
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            # Navigate to the real search page — Shopee's own JS makes the API call
            # with proper session cookies, bypassing bot detection on the API endpoint.
            await page.goto(search_page_url, wait_until="networkidle", timeout=30000)
        finally:
            await browser.close()

    if not captured:
        raise ValueError("Could not capture search API response from Shopee. Bot detection may have triggered.")

    if not captured.get("items"):
        raise ValueError(
            f"No items in response. Top-level keys: {list(captured.keys())}. "
            f"Preview: {json.dumps(captured)[:300]}"
        )

    items = captured.get("items") or []
    results = []
    for item in items[:limit]:
        basic = item.get("item_basic") or {}
        item_id = basic.get("itemid")
        shop_id = basic.get("shopid")
        name = basic.get("name", "")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        url = f"{BASE}/{slug}-i.{shop_id}.{item_id}" if item_id and shop_id else ""

        results.append({
            "name": name,
            "price": _parse_price(basic.get("price")),
            "original_price": _parse_price(basic.get("price_before_discount") or basic.get("price")),
            "discount": basic.get("discount"),
            "rating": round(basic.get("item_rating", {}).get("rating_star", 0), 1),
            "review_count": basic.get("item_rating", {}).get("rating_count", [0])[0] if basic.get("item_rating") else 0,
            "sold_count": basic.get("historical_sold"),
            "monthly_sold": basic.get("sold"),
            "location": basic.get("shop_location"),
            "url": url,
            "image_url": f"https://cf.shopee.ph/file/{basic['image']}" if basic.get("image") else None,
            "seller": basic.get("shop_name"),
            "is_mall": basic.get("shopee_verified", False),
            "in_stock": basic.get("stock", 0) > 0,
            "item_id": item_id,
            "shop_id": shop_id,
        })

    return results


async def _get_detail(item_id: int, shop_id: int) -> dict:
    product_page_url = f"{BASE}/i.{shop_id}.{item_id}"
    captured: dict | None = None

    async with async_playwright() as pw:
        browser, context = await _new_context(pw)
        page = await context.new_page()

        async def on_response(resp):
            nonlocal captured
            if "api/v4/item/get" in resp.url and captured is None:
                try:
                    captured = await resp.json()
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await page.goto(product_page_url, wait_until="networkidle", timeout=30000)
        finally:
            await browser.close()

    if not captured:
        raise ValueError(f"Could not capture item API response for item {item_id}.")

    item = (captured.get("data") or captured.get("item") or {})
    models = item.get("models") or []
    first_model = models[0] if models else {}

    return {
        "item_id": item_id,
        "shop_id": shop_id,
        "title": item.get("name"),
        "description": item.get("description"),
        "brand": item.get("brand"),
        "price": _parse_price(first_model.get("price") or item.get("price")),
        "original_price": _parse_price(item.get("price_before_discount") or item.get("price")),
        "stock": item.get("stock"),
        "rating": item.get("item_rating", {}).get("rating_star"),
        "review_count": item.get("item_rating", {}).get("rating_count", [0])[0] if item.get("item_rating") else 0,
        "sold": item.get("historical_sold"),
        "seller": item.get("shop_name"),
        "location": item.get("shop_location"),
        "categories": [c.get("display_name") for c in (item.get("categories") or [])],
        "images": [f"https://cf.shopee.ph/file/{img}" for img in (item.get("images") or [])],
        "url": f"{BASE}/{re.sub(r'[^a-z0-9]+', '-', (item.get('name') or '').lower()).strip('-')}-i.{shop_id}.{item_id}",
    }


def search_products(keyword: str, limit: int = 10, sort_by: str = "sales") -> list[dict]:
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _search(keyword, limit, sort_by))
            return future.result()
    except RuntimeError:
        return asyncio.run(_search(keyword, limit, sort_by))


def get_product_detail(item_id: int, shop_id: int) -> dict:
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _get_detail(item_id, shop_id))
            return future.result()
    except RuntimeError:
        return asyncio.run(_get_detail(item_id, shop_id))
