"""
Tradovate API client.

Usage:
    client = TradovateClient.from_env()
    fills = client.get_fills()
"""

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from app.tradovate.auth import TradovateToken, get_valid_token

load_dotenv()


@dataclass
class TradovateClient:
    credentials: dict

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "TradovateClient":
        """Build a client from environment variables (or a .env file)."""
        credentials = {
            "username": os.environ["TRADOVATE_USERNAME"],
            "password": os.environ["TRADOVATE_PASSWORD"],
            "app_id": os.environ.get("TRADOVATE_APP_ID", "Sample App"),
            "app_version": os.environ.get("TRADOVATE_APP_VERSION", "1.0"),
            "cid": int(os.environ.get("TRADOVATE_CID", "8")),
            "secret": os.environ["TRADOVATE_SECRET"],
            "env": os.environ.get("TRADOVATE_ENV", "demo"),
        }
        return cls(credentials=credentials)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _token(self) -> TradovateToken:
        return get_valid_token(self.credentials)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token().access_token}"}

    def _get(self, path: str, params: dict = None) -> Any:
        url = f"{self._token().base_url()}{path}"
        response = requests.get(url, headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def get_fills(self) -> list[dict]:
        """
        Fetch all trade executions (fills) for the account.

        Each fill contains: id, orderId, contractId, timestamp, price,
        qty, side ('Buy' or 'Sell'), and more.
        """
        return self._get("/execution/list")

    def get_accounts(self) -> list[dict]:
        """List all accounts associated with this login."""
        return self._get("/account/list")

    def get_positions(self) -> list[dict]:
        """Return all open positions."""
        return self._get("/position/list")

    def get_orders(self) -> list[dict]:
        """Return all orders (open and historical)."""
        return self._get("/order/list")
