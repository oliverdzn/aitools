"""
Lazada public product scraper for lazada.com.ph
Uses Playwright (headless Chromium) to bypass Lazada's bot detection.

Lazada uses a JS challenge (`_____tmd_____/punish`) that blocks plain HTTP requests.
A real browser (Playwright) passes this challenge automatically.

Install:
    pip install playwright
    playwright install chromium
    playwright install-deps chromium
"""
import asyncio
import json
import re
from typing import Any

from playwright.async_api import async_playwright

BASE = "https://www.lazada.com.ph"

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-PH', 'en'] });
window.chrome = { runtime: {} };
"""


def _parse_price(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r"[^\d.]", "", str(val))
    return float(cleaned) if cleaned else None


async def _search(keyword: str, limit: int, sort: str) -> list[dict]:
    sort_map = {
        "popularity": "pop",
        "priceasc": "priceasc",
        "pricedesc": "pricedesc",
        "rating": "rating",
        "new": "new",
        "bestsell": "bestsell",
    }
    sort_param = sort_map.get(sort, "pop")
    url = f"{BASE}/catalog/?q={keyword.replace(' ', '+')}&ajax=true&sort={sort_param}"

    async with async_playwright() as pw:
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
        page = await context.new_page()

        try:
            # Visit homepage first to get session cookies
            await page.goto(BASE, wait_until="domcontentloaded", timeout=20000)

            # Now hit the search API — Playwright passes the bot challenge automatically
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            body = await response.text() if response else ""

            # Response should be JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                # Fallback: JSON might be embedded in HTML
                match = re.search(r'window\.pageData\s*=\s*(\{.*?\});\s*</script>', body, re.DOTALL)
                if not match:
                    raise ValueError(f"Unexpected response from Lazada (length={len(body)}). Bot detection may have triggered.")
                data = json.loads(match.group(1))

        finally:
            await browser.close()

    items = data.get("mods", {}).get("listItems", [])
    results = []
    for item in items[:limit]:
        product_url = item.get("productUrl") or item.get("itemUrl") or ""
        if product_url and not product_url.startswith("http"):
            product_url = "https:" + product_url

        results.append({
            "name": item.get("name"),
            "price": _parse_price(item.get("price")),
            "original_price": _parse_price(item.get("originalPrice")),
            "discount": item.get("discount"),
            "rating": item.get("ratingScore"),
            "review_count": item.get("review"),
            "sold_count": item.get("itemSoldCntShow"),
            "location": item.get("location"),
            "url": product_url,
            "image_url": item.get("image"),
            "seller": item.get("sellerName"),
            "is_sponsored": item.get("isSponsored", False),
            "in_stock": item.get("inStock", True),
        })

    return results


async def _get_detail(product_url: str) -> dict:
    clean_url = product_url.split("?")[0]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-PH",
            timezone_id="Asia/Manila",
        )
        await context.add_init_script(_STEALTH_SCRIPT)
        page = await context.new_page()

        try:
            await page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
            await page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)

            # Extract embedded JSON from page
            page_data = await page.evaluate("""
                () => {
                    if (window.__global_data) return window.__global_data;
                    if (window.pageData) return window.pageData;
                    return null;
                }
            """)

            if not page_data:
                # Fallback: scrape visible DOM
                title = await page.title()
                price_el = await page.query_selector('.pdp-price_type_normal')
                price_text = await price_el.inner_text() if price_el else None
                return {
                    "url": product_url,
                    "title": title,
                    "price": _parse_price(price_text),
                    "_note": "Partial data — JS data not available",
                }

            product = page_data.get("product", {})
            skus = page_data.get("skus", [{}])
            sku = skus[0] if skus else {}
            seller = page_data.get("seller", {})

            return {
                "url": product_url,
                "title": product.get("title"),
                "brand": (product.get("brand") or {}).get("name") if isinstance(product.get("brand"), dict) else product.get("brand"),
                "price": _parse_price(sku.get("price")),
                "original_price": _parse_price(sku.get("originalPrice")),
                "in_stock": sku.get("quantity", 0) > 0,
                "rating": page_data.get("review", {}).get("ratings"),
                "review_count": page_data.get("review", {}).get("count"),
                "seller": seller.get("name"),
                "description": product.get("description"),
                "images": [img.get("image") for img in product.get("images", []) if img.get("image")],
            }
        finally:
            await browser.close()


# Sync wrappers for use from synchronous MCP tool handlers
def search_products(keyword: str, limit: int = 20, sort: str = "popularity") -> list[dict]:
    return asyncio.run(_search(keyword, limit, sort))


def get_product_detail(url: str) -> dict:
    return asyncio.run(_get_detail(url))
