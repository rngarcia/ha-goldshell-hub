"""Data update coordinator for Goldshell Hub."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GoldshellAuthError,
    GoldshellConnectionError,
    GoldshellError,
    GoldshellHubApi,
)
from .const import CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GoldshellHubCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls the hub and exposes machines keyed by MAC address."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        self.entry = entry
        self.api = GoldshellHubApi(
            async_get_clientsession(hass), token=entry.data[CONF_TOKEN]
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch machines and key them by MAC (falling back to dev_name)."""
        try:
            machines = await self.api.async_get_machines()
        except GoldshellAuthError as err:
            # Token expired: trigger the reauth flow (re-scan the QR).
            raise ConfigEntryAuthFailed(str(err)) from err
        except GoldshellConnectionError as err:
            raise UpdateFailed(f"Cannot reach Goldshell Hub: {err}") from err
        except GoldshellError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[str, dict[str, Any]] = {}
        for machine in machines:
            key = machine.get("mac") or machine.get("dev_name")
            if key:
                result[key] = machine
        return result
