"""
Lazada public product scraper for lazada.com.ph
Uses Lazada's internal JSON API directly — no Playwright/Chromium needed.
100% free, runs from your local machine.

How it works:
  Lazada's website loads search results via an internal API:
    GET https://www.lazada.com.ph/catalog/?q={keyword}&ajax=true
  This returns structured JSON with product listings — same data the browser sees.
  We call it directly with httpx + browser-like headers.
"""
import httpx
import re
from typing import Any

BASE = "https://www.lazada.com.ph"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-PH,en;q=0.9",
    "Referer": "https://www.lazada.com.ph/",
    "x-locale": "en_PH",
}


def _parse_price(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    # Strip currency symbols and commas
    cleaned = re.sub(r"[^\d.]", "", str(val))
    return float(cleaned) if cleaned else None


def search_products(keyword: str, limit: int = 20, sort: str = "popularity") -> list[dict]:
    """
    Search lazada.com.ph and return public product listings.
    sort options: popularity | priceasc | pricedesc | rating | new | bestsell

    Returns list of dicts: {
        name, price, original_price, discount, rating, review_count,
        sold_count, location, url, image_url, seller, is_sponsored, in_stock
    }
    """
    sort_map = {
        "popularity": "pop",
        "priceasc": "priceasc",
        "pricedesc": "pricedesc",
        "rating": "rating",
        "new": "new",
        "bestsell": "bestsell",
    }
    params = {
        "q": keyword,
        "ajax": "true",
        "sort": sort_map.get(sort, "pop"),
    }

    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
        r = client.get(f"{BASE}/catalog/", params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("mods", {}).get("listItems", [])
    results = []
    for item in items[:limit]:
        url = item.get("productUrl") or item.get("itemUrl") or ""
        if url and not url.startswith("http"):
            url = "https:" + url

        results.append({
            "name": item.get("name"),
            "price": _parse_price(item.get("price")),
            "original_price": _parse_price(item.get("originalPrice")),
            "discount": item.get("discount"),
            "rating": item.get("ratingScore"),
            "review_count": item.get("review"),
            "sold_count": item.get("itemSoldCntShow"),
            "location": item.get("location"),
            "url": url,
            "image_url": item.get("image"),
            "seller": item.get("sellerName"),
            "is_sponsored": item.get("isSponsored", False),
            "in_stock": not item.get("inStock") is False,
        })

    return results


def get_product_detail(product_url: str) -> dict:
    """
    Get full details of a Lazada PH product page.
    Hits the product URL with ajax=true to get structured JSON.
    """
    # Ensure clean URL
    url = product_url.split("?")[0]

    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=20) as client:
        r = client.get(url, params={"ajax": "true"})
        r.raise_for_status()

        content_type = r.headers.get("content-type", "")
        if "json" in content_type:
            data = r.json()
        else:
            # Fall back to HTML parsing for key fields
            text = r.text
            import re as _re
            price_match = _re.search(r'"price":\s*"?([\d.]+)"?', text)
            name_match = _re.search(r'"subject":\s*"([^"]+)"', text)
            return {
                "url": product_url,
                "title": name_match.group(1) if name_match else None,
                "price": float(price_match.group(1)) if price_match else None,
                "_note": "Partial data — page returned HTML instead of JSON",
            }

    # Extract from JSON response
    page_data = data.get("pageData", {})
    product = page_data.get("product", {})
    skus = page_data.get("skus", [{}])
    sku = skus[0] if skus else {}
    seller = page_data.get("seller", {})

    return {
        "url": product_url,
        "title": product.get("title"),
        "brand": product.get("brand", {}).get("name") if isinstance(product.get("brand"), dict) else product.get("brand"),
        "price": _parse_price(sku.get("price")),
        "original_price": _parse_price(sku.get("originalPrice")),
        "in_stock": sku.get("quantity", 0) > 0,
        "rating": page_data.get("review", {}).get("ratings"),
        "review_count": page_data.get("review", {}).get("count"),
        "seller": seller.get("name"),
        "seller_rating": seller.get("sellerScore"),
        "description": product.get("description"),
        "images": [img.get("image") for img in product.get("images", []) if img.get("image")],
        "warranty": product.get("warranty"),
    }
