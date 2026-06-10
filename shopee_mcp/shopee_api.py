"""
Shopee Open Platform API wrapper for shopee.ph (Philippines).
Uses API v2 with HMAC-SHA256 signing.

Credentials required:
  SHOPEE_PARTNER_ID    - numeric partner ID from open.shopee.com
  SHOPEE_PARTNER_KEY   - live key from open.shopee.com
  SHOPEE_ACCESS_TOKEN  - OAuth access token (shop-level)
  SHOPEE_SHOP_ID       - numeric shop ID
"""
import hashlib
import hmac
import time
from typing import Any

import httpx

BASE_URL = "https://partner.shopeemobile.com/api/v2"


class ShopeeAPIError(Exception):
    def __init__(self, error: str, message: str):
        self.error = error
        self.message = message
        super().__init__(f"{error}: {message}")


class ShopeeClient:
    def __init__(self, partner_id: int, partner_key: str, access_token: str, shop_id: int):
        self.partner_id = partner_id
        self.partner_key = partner_key
        self.access_token = access_token
        self.shop_id = shop_id
        self._client = httpx.Client(timeout=30)

    def close(self):
        self._client.close()

    def _sign(self, api_path: str, timestamp: int, is_shop: bool = True) -> str:
        if is_shop:
            base = f"{self.partner_id}{api_path}{timestamp}{self.access_token}{self.shop_id}"
        else:
            base = f"{self.partner_id}{api_path}{timestamp}"
        return hmac.new(
            self.partner_key.encode(),
            base.encode(),
            hashlib.sha256,
        ).hexdigest()


    def _common_params(self, api_path: str, is_shop: bool = True) -> dict:
        ts = int(time.time())
        params = {
            "partner_id": self.partner_id,
            "timestamp": ts,
            "sign": self._sign(api_path, ts, is_shop),
        }
        if is_shop:
            params["access_token"] = self.access_token
            params["shop_id"] = self.shop_id
        return params

    def _get(self, path: str, extra: dict | None = None, is_shop: bool = True) -> dict:
        params = self._common_params(path, is_shop)
        if extra:
            params.update(extra)
        resp = self._client.get(BASE_URL + path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") and data["error"] != "":
            raise ShopeeAPIError(data["error"], data.get("message", ""))
        return data.get("response", data)

    def _post(self, path: str, body: dict, extra_params: dict | None = None) -> dict:
        params = self._common_params(path)
        if extra_params:
            params.update(extra_params)
        resp = self._client.post(BASE_URL + path, params=params, json=body)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") and data["error"] != "":
            raise ShopeeAPIError(data["error"], data.get("message", ""))
        return data.get("response", data)

    # ── Shop ──────────────────────────────────────────────────────────────────

    def get_shop_info(self) -> dict:
        return self._get("/shop/get_shop_info")

    # ── Products ──────────────────────────────────────────────────────────────

    def get_item_list(self, offset: int = 0, limit: int = 20, item_status: str = "NORMAL") -> dict:
        return self._get("/product/get_item_list", {
            "offset": offset,
            "page_size": limit,
            "item_status": item_status,
        })

    def get_item_base_info(self, item_ids: list[int]) -> dict:
        return self._get("/product/get_item_base_info", {
            "item_id_list": ",".join(str(i) for i in item_ids),
        })

    def update_price(self, item_id: int, model_id: int, original_price: float) -> dict:
        return self._post("/product/update_price", {
            "item_id": item_id,
            "price_list": [{"model_id": model_id, "original_price": original_price}],
        })

    def update_stock(self, item_id: int, model_id: int, normal_stock: int) -> dict:
        return self._post("/product/update_stock", {
            "item_id": item_id,
            "stock_list": [{"model_id": model_id, "normal_stock": normal_stock}],
        })

    # ── Orders ────────────────────────────────────────────────────────────────

    def get_order_list(
        self,
        time_range_field: str = "create_time",
        time_from: int | None = None,
        time_to: int | None = None,
        order_status: str | None = None,
        page_size: int = 20,
        cursor: str = "",
    ) -> dict:
        now = int(time.time())
        params: dict[str, Any] = {
            "time_range_field": time_range_field,
            "time_from": time_from or (now - 30 * 86400),
            "time_to": time_to or now,
            "page_size": page_size,
            "cursor": cursor,
        }
        if order_status:
            params["order_status"] = order_status
        return self._get("/order/get_order_list", params)

    def get_order_detail(self, order_sn_list: list[str]) -> dict:
        return self._get("/order/get_order_detail", {
            "order_sn_list": ",".join(order_sn_list),
        })

    # ── Auth ──────────────────────────────────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> dict:
        path = "/auth/access_token/get"
        ts = int(time.time())
        sign = hmac.new(
            self.partner_key.encode(),
            f"{self.partner_id}{path}{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        resp = self._client.post(
            BASE_URL + path,
            params={"partner_id": self.partner_id, "timestamp": ts, "sign": sign},
            json={
                "shop_id": self.shop_id,
                "partner_id": self.partner_id,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error") and data["error"] != "":
            raise ShopeeAPIError(data["error"], data.get("message", ""))
        return data
