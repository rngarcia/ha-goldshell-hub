"""Config flow for Goldshell Hub (QR-code login)."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoldshellError, GoldshellHubApi, GoldshellLoginTimeout
from .const import CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

_EMPTY_SCHEMA = vol.Schema({})


def _make_qr_data_uri(payload: str) -> str:
    """Render ``payload`` as a PNG QR code and return a data: URI (blocking)."""
    import qrcode  # lazily imported; declared in manifest requirements

    img = qrcode.make(payload)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


class GoldshellHubConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldshell Hub."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise transient login state."""
        self._api: GoldshellHubApi | None = None
        self._login_task: asyncio.Task[str] | None = None
        self._code: str | None = None
        self._qr: str | None = None
        self._q_link: str | None = None
        self._token: str | None = None

    async def _async_new_code(self) -> str | None:
        """Request a fresh QR login code; return an abort reason on failure."""
        self._api = GoldshellHubApi(async_get_clientsession(self.hass))
        try:
            data = await self._api.async_request_login_code()
        except GoldshellError:
            return "cannot_connect"
        self._code = data.get("code")
        self._q_link = data.get("q_link", "")
        if not self._code or not self._q_link:
            return "cannot_connect"
        self._qr = await self.hass.async_add_executor_job(
            _make_qr_data_uri, self._q_link
        )
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the QR code; proceed to polling when the user submits."""
        if self._code is None:
            if (reason := await self._async_new_code()) is not None:
                return self.async_abort(reason=reason)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_EMPTY_SCHEMA,
                description_placeholders={
                    "qr_code": f"![QR]({self._qr})",
                    "q_link": self._q_link or "",
                },
            )

        return await self.async_step_wait()

    async def async_step_wait(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Poll /user/check until the QR is approved."""
        assert self._api is not None and self._code is not None
        if self._login_task is None:
            self._login_task = self.hass.async_create_task(
                self._api.async_wait_for_login(self._code)
            )

        if not self._login_task.done():
            return self.async_show_progress(
                step_id="wait",
                progress_action="wait_for_scan",
                progress_task=self._login_task,
            )

        try:
            self._token = self._login_task.result()
        except GoldshellLoginTimeout:
            self._reset_login()
            return self.async_show_progress_done(next_step_id="timeout")
        except GoldshellError:
            self._reset_login()
            return self.async_show_progress_done(next_step_id="login_error")

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the token, dedupe by account, create/update the entry."""
        assert self._token is not None
        self._api = GoldshellHubApi(
            async_get_clientsession(self.hass), token=self._token
        )
        try:
            info = await self._api.async_get_userinfo()
        except GoldshellError:
            info = {}

        unique_id = str(info.get("uid") or info.get("id") or "account")
        await self.async_set_unique_id(unique_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data={CONF_TOKEN: self._token}
            )

        self._abort_if_unique_id_configured()
        title = info.get("nickname") or info.get("email") or "Goldshell Hub"
        return self.async_create_entry(title=title, data={CONF_TOKEN: self._token})

    async def async_step_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer a retry after the QR code expired."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="timeout", data_schema=_EMPTY_SCHEMA)

    async def async_step_login_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer a retry after a login error."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="login_error", data_schema=_EMPTY_SCHEMA)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle an expired token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm, then re-run the QR login."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=_EMPTY_SCHEMA
            )
        return await self.async_step_user()

    def _reset_login(self) -> None:
        """Clear transient login state so a retry starts fresh."""
        self._login_task = None
        self._code = None
        self._qr = None
        self._q_link = None
