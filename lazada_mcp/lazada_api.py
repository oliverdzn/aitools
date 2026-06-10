"""
Lazada Open Platform API wrapper (LazOP)
Targets: lazada.com.ph (Philippines)
Docs: https://open.lazada.com/apps/doc/api
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

GATEWAY = "https://api.lazada.com.ph/rest"


def _sign(app_secret: str, api_path: str, params: dict) -> str:
    """Compute HMAC-SHA256 signature per LazOP spec."""
    sorted_params = sorted(params.items())
    concatenated = api_path + "".join(f"{k}{v}" for k, v in sorted_params)
    return hmac.new(
        app_secret.encode("utf-8"),
        concatenated.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class LazadaAPIError(Exception):
    def __init__(self, code: str, message: str, request_id: str = ""):
        super().__init__(f"[{code}] {message} (request_id={request_id})")
        self.code = code
        self.message = message
        self.request_id = request_id


class LazadaClient:
    def __init__(self, app_key: str, app_secret: str, access_token: str | None = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self._http = httpx.Client(timeout=30)

    def _call(self, api_path: str, params: dict | None = None, method: str = "GET") -> dict:
        params = params or {}
        base_params = {
            "app_key": self.app_key,
            "timestamp": _timestamp(),
            "sign_method": "sha256",
        }
        if self.access_token:
            base_params["access_token"] = self.access_token

        all_params = {**base_params, **params}
        all_params["sign"] = _sign(self.app_secret, api_path, all_params)

        url = GATEWAY + api_path
        if method == "GET":
            response = self._http.get(url, params=all_params)
        else:
            response = self._http.post(url, data=all_params)

        response.raise_for_status()
        data = response.json()

        if data.get("code") and data["code"] != "0":
            raise LazadaAPIError(
                data.get("code", "UNKNOWN"),
                data.get("message", "Unknown error"),
                data.get("request_id", ""),
            )
        return data

    # ── Auth ──────────────────────────────────────────────────────────────────

    def generate_access_token(self, auth_code: str) -> dict:
        """Exchange OAuth auth code for access + refresh tokens."""
        return self._call("/auth/token/create", {"code": auth_code}, method="POST")

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        return self._call(
            "/auth/token/refresh",
            {"refresh_token": refresh_token},
            method="POST",
        )

    # ── Products ──────────────────────────────────────────────────────────────

    def get_products(
        self,
        filter: str = "all",
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
        created_after: str | None = None,
    ) -> dict:
        """
        Get seller's own products.
        filter: all | live | inactive | deleted | image-missing | pending | rejected | sold-out
        """
        params: dict = {"filter": filter, "limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if created_after:
            params["created_after"] = created_after
        return self._call("/products/get", params)

    def update_price_quantity(self, seller_sku: str, price: float, quantity: int) -> dict:
        """Update price and stock for a SKU."""
        payload = json.dumps({
            "Request": {
                "Product": {
                    "Skus": {
                        "Sku": [
                            {
                                "ItemId": "",
                                "SkuId": "",
                                "SellerId": self.app_key,
                                "SellerSku": seller_sku,
                                "price": price,
                                "quantity": quantity,
                            }
                        ]
                    }
                }
            }
        })
        return self._call("/product/price_quantity/update", {"payload": payload}, method="POST")

    def get_category_tree(self) -> dict:
        """Get the full Lazada PH category tree."""
        return self._call("/category/tree/get")

    def get_brands(self, keyword: str | None = None, limit: int = 50) -> dict:
        """Search for brands."""
        params: dict = {"limit": limit}
        if keyword:
            params["keyword"] = keyword
        return self._call("/brands/query", params)

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_orders(
        self,
        status: str | None = None,
        created_after: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """
        Get orders.
        status: unpaid | pending | ready_to_ship | delivered | returned | shipped | failed | canceled
        created_after: ISO8601 string e.g. "2024-01-01T00:00:00+08:00"
        """
        params: dict = {"limit": limit, "offset": offset, "sort_by": "created_at", "sort_direction": "DESC"}
        if status:
            params["status"] = status
        if created_after:
            params["created_after"] = created_after
        return self._call("/orders/get", params)

    def get_order(self, order_id: int) -> dict:
        """Get a single order's details."""
        return self._call("/order/get", {"order_id": order_id})

    def get_order_items(self, order_id: int) -> dict:
        """Get items for a specific order."""
        return self._call("/order/items/get", {"order_id": order_id})

    # ── Seller ────────────────────────────────────────────────────────────────

    def get_seller(self) -> dict:
        """Get authenticated seller info."""
        return self._call("/seller/get")

    def close(self):
        self._http.close()
