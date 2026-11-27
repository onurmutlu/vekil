"""Trendyol Store API client for SoruPilot."""
import aiohttp
import json
from typing import Optional, Dict, Any


class TrendyolClient:
    """Trendyol Seller API client for fetching store & product data."""

    BASE_URL = "https://seller-api.trendyol.com/api"

    def __init__(self, api_key: str, api_secret: str, seller_id: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.seller_id = seller_id

    async def get_store_info(self) -> Dict[str, Any]:
        """Fetch seller store metadata from Trendyol."""
        # TODO: Implement Trendyol Seller API call
        # Endpoint: GET /api/seller/info
        # Headers: X-API-KEY, X-API-SECRET
        return {
            "seller_id": self.seller_id,
            "store_name": "Example Store",
            "category": "Elektronik",
            "rating": 4.5,
        }

    async def get_products(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Fetch products from seller store."""
        # TODO: Implement Trendyol Seller API
        # Endpoint: GET /api/seller/products
        return []

    async def search_product(self, query: str) -> Optional[Dict[str, Any]]:
        """Search for a product in seller store."""
        # TODO: Search products
        return None

    async def get_faq(self) -> str:
        """Build FAQ/knowledge base from store data."""
        products = await self.get_products()
        store = await self.get_store_info()

        # Format product catalog as text for knowledge base
        knowledge = f"""
TRENDYOL MAĞAZA: {store.get('store_name', 'Mağaza')}
Kategori: {store.get('category', 'Ürünler')}
Puan: {store.get('rating', 'N/A')}

ÜRÜNLER:
"""
        for prod in products[:20]:  # Limit to 20 for token efficiency
            knowledge += f"\n- {prod.get('title', 'Ürün')}: ₺{prod.get('price', 'fiyat sorunuz')} (Stok: {prod.get('stock', '?')})"

        knowledge += "\n\nMüşteri temasa geçmek için: Trendyol mesaj sistemi veya satıcı paneli"
        return knowledge


class TrendyolOAuth:
    """Trendyol OAuth 2.0 flow for seller authentication."""

    AUTHORIZE_URL = "https://seller-oauth.trendyol.com/oauth/authorize"
    TOKEN_URL = "https://seller-oauth.trendyol.com/oauth/token"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorization_url(self, state: str) -> str:
        """Generate Trendyol OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTHORIZE_URL}?{query_string}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        # TODO: Implement token exchange with Trendyol
        return {
            "access_token": "",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
