"""
Tradovate authentication: login, token storage, and refresh.

Flow:
  1. Call login() with your credentials → get an access token.
  2. The token has an expiry time returned by the API.
  3. Before each request, call get_valid_token() — it auto-refreshes when
     the token is within 5 minutes of expiring.
  4. Tokens are persisted to a local JSON file so you don't re-login on
     every script run.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

TOKEN_FILE = Path(__file__).parent.parent.parent / ".tradovate_token.json"
REFRESH_BUFFER_SECONDS = 300  # refresh 5 min before expiry

BASE_URLS = {
    "demo": "https://demo.tradovateapi.com/v1",
    "live": "https://live.tradovateapi.com/v1",
}


@dataclass
class TradovateToken:
    access_token: str
    expiration_time: str  # ISO 8601 string from the API
    env: str              # "demo" or "live"

    def is_expired(self) -> bool:
        expiry = datetime.fromisoformat(self.expiration_time.replace("Z", "+00:00"))
        now = datetime.now(tz=timezone.utc)
        seconds_left = (expiry - now).total_seconds()
        return seconds_left < REFRESH_BUFFER_SECONDS

    def base_url(self) -> str:
        return BASE_URLS[self.env]


def _save_token(token: TradovateToken) -> None:
    TOKEN_FILE.write_text(json.dumps(asdict(token), indent=2))


def _load_token() -> Optional[TradovateToken]:
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    return TradovateToken(**data)


def login(
    username: str,
    password: str,
    app_id: str,
    app_version: str,
    cid: int,
    secret: str,
    env: str = "demo",
) -> TradovateToken:
    """Authenticate with Tradovate and return a stored token."""
    url = f"{BASE_URLS[env]}/auth/accesstokenrequest"
    payload = {
        "name": username,
        "password": password,
        "appId": app_id,
        "appVersion": app_version,
        "cid": cid,
        "sec": secret,
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()

    if "errorText" in data:
        raise ValueError(f"Tradovate login failed: {data['errorText']}")

    token = TradovateToken(
        access_token=data["accessToken"],
        expiration_time=data["expirationTime"],
        env=env,
    )
    _save_token(token)
    return token


def refresh_token(token: TradovateToken) -> TradovateToken:
    """Exchange a still-valid token for a new one with a fresh expiry."""
    url = f"{token.base_url()}/auth/renewaccesstoken"
    response = requests.get(
        url, headers={"Authorization": f"Bearer {token.access_token}"}
    )
    response.raise_for_status()

    data = response.json()
    refreshed = TradovateToken(
        access_token=data["accessToken"],
        expiration_time=data["expirationTime"],
        env=token.env,
    )
    _save_token(refreshed)
    return refreshed


def get_valid_token(credentials: dict) -> TradovateToken:
    """
    Return a ready-to-use token. Loads from disk if available, refreshes if
    near expiry, or logs in fresh if none exists.

    credentials dict keys: username, password, app_id, app_version, cid,
                           secret, env
    """
    token = _load_token()

    if token is None or token.env != credentials.get("env", "demo"):
        print("No stored token found — logging in...")
        return login(**credentials)

    if token.is_expired():
        print("Token near expiry — refreshing...")
        try:
            return refresh_token(token)
        except Exception:
            print("Refresh failed — logging in again...")
            return login(**credentials)

    return token
