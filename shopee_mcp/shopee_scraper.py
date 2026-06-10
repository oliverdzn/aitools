"""
Shopee public product scraper for shopee.ph
Uses Playwright (headless Chromium) to bypass Shopee's bot detection,
then calls Shopee's internal search/item JSON API.
"""
import asyncio
import json
import re
from typing import Any

from playwright.async_api import async_playwright

BASE = "https://shopee.ph"
SEARCH_URL = BASE + "/api/v4/search/search_items"
ITEM_URL = BASE + "/api/v4/item/get"

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
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-PH",
        timezone_id="Asia/Manila",
        viewport={"width": 1280, "height": 800},
    )
    await context.add_init_script(_STEALTH_SCRIPT)
    return browser, context


async def _search(keyword: str, limit: int = 10, sort_by: str = "sales") -> list[dict]:
    sort_map = {"sales": "sales", "price_asc": "price", "price_desc": "price", "newest": "ctime", "relevance": "relevancy"}
    sort_param = sort_map.get(sort_by, "sales")
    order = "asc" if sort_by == "price_asc" else "desc"

    params = (
        f"?by={sort_param}&keyword={keyword.replace(' ', '%20')}"
        f"&limit={min(limit, 60)}&newest=0&order={order}"
        f"&page_type=search&scenario=PAGE_OTHERS&version=2"
    )

    async with async_playwright() as pw:
        browser, context = await _new_context(pw)
        page = await context.new_page()
        try:
            # Visit homepage first to get session cookies
            await page.goto(BASE, wait_until="domcontentloaded", timeout=20000)

            # Intercept the API response via fetch
            response = await page.goto(SEARCH_URL + params, wait_until="domcontentloaded", timeout=20000)
            body = await response.text() if response else ""

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError(f"Non-JSON response from Shopee search (len={len(body)}). Bot detection may have triggered.")
        finally:
            await browser.close()

    items = data.get("items") or []
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
    async with async_playwright() as pw:
        browser, context = await _new_context(pw)
        page = await context.new_page()
        try:
            await page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
            response = await page.goto(
                f"{ITEM_URL}?itemid={item_id}&shopid={shop_id}",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            body = await response.text() if response else ""
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError(f"Non-JSON response from Shopee item API (len={len(body)}).")
        finally:
            await browser.close()

    item = (data.get("data") or data.get("item") or {})
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
