"""Thin async client for the Goldshell Hub cloud API.

The hub exposes a JSON API under https://hub.goldshell.com/api/v1. It is not
publicly documented; the endpoints and payloads here were observed from the
hub's own single-page app. Responses use a ``{"code": 0, "message": "...",
"data": {...}}`` envelope; ``code`` is 0 on success and 401 (often with
``error": "Invalid token"``) when the token is missing or expired.

Authentication is a ~30-day JWT sent in a bare ``token`` header. There is no
refresh endpoint, so when it expires the integration re-runs the QR login.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import (
    API_BASE,
    AUTH_HEADER,
    EP_CHECK,
    EP_CODE,
    EP_MACHINES,
    EP_USERINFO,
    QR_LOGIN_TIMEOUT,
    QR_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20


class GoldshellError(Exception):
    """Base error for the Goldshell Hub client."""


class GoldshellAuthError(GoldshellError):
    """Raised when the token is missing, invalid or expired."""


class GoldshellConnectionError(GoldshellError):
    """Raised when the hub cannot be reached."""


class GoldshellLoginTimeout(GoldshellError):
    """Raised when the QR login code expires before it is approved."""


class GoldshellHubApi:
    """Minimal client around the endpoints the integration needs."""

    def __init__(self, session: ClientSession, token: str | None = None) -> None:
        """Initialise with an aiohttp session and optionally an existing token."""
        self._session = session
        self._token = token

    @property
    def token(self) -> str | None:
        """Return the current access token, if any."""
        return self._token

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        authed: bool = True,
    ) -> dict[str, Any]:
        """Perform a request and return the envelope's ``data`` payload."""
        headers = {"Accept": "application/json"}
        if authed:
            if not self._token:
                raise GoldshellAuthError("No token configured")
            headers[AUTH_HEADER] = self._token

        url = f"{API_BASE}{endpoint}"
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                # The hub returns 200 with code!=0 for most logical errors, but
                # also sometimes a real 401, so inspect both.
                payload: dict[str, Any] = await resp.json(content_type=None)
        except asyncio.TimeoutError as err:
            raise GoldshellConnectionError(f"Timeout talking to {url}") from err
        except ClientError as err:
            raise GoldshellConnectionError(str(err)) from err

        code = payload.get("code")
        if code in (401, 403) or payload.get("error") == "Invalid token":
            raise GoldshellAuthError(payload.get("error") or "Invalid token")
        if code not in (0, None):
            raise GoldshellError(
                f"{endpoint} returned code={code}: {payload.get('message') or payload.get('error')}"
            )
        return payload.get("data") or {}

    # ------------------------------------------------------------------ #
    # QR login
    # ------------------------------------------------------------------ #
    async def async_request_login_code(self) -> dict[str, Any]:
        """Start a QR login. Returns ``{code, q_link, expired_time, ...}``."""
        return await self._request("GET", EP_CODE, authed=False)

    async def async_check_login(self, code: str) -> str | None:
        """Poll once. Returns the access token when approved, else ``None``."""
        data = await self._request(
            "GET", EP_CHECK, params={"code": code}, authed=False
        )
        token = data.get("access_token") or ""
        return token or None

    async def async_wait_for_login(self, code: str) -> str:
        """Poll ``/user/check`` until the QR is approved, then return the token."""
        waited = 0
        while waited < QR_LOGIN_TIMEOUT:
            token = await self.async_check_login(code)
            if token:
                self._token = token
                return token
            await asyncio.sleep(QR_POLL_INTERVAL)
            waited += QR_POLL_INTERVAL
        raise GoldshellLoginTimeout("QR login code expired before approval")

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #
    async def async_get_userinfo(self) -> dict[str, Any]:
        """Return the account info (used to validate a token and name the entry)."""
        return await self._request("GET", EP_USERINFO)

    async def async_get_machines(self) -> list[dict[str, Any]]:
        """Return the list of machines on the account."""
        data = await self._request(
            "GET", EP_MACHINES, params={"page": 1, "pagesize": 100}
        )
        machines = data.get("list")
        return machines if isinstance(machines, list) else []
