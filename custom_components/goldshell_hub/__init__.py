"""The Goldshell Hub integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import GoldshellHubCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GoldshellHubConfigEntry = ConfigEntry[GoldshellHubCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GoldshellHubConfigEntry
) -> bool:
    """Set up Goldshell Hub from a config entry."""
    coordinator = GoldshellHubCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoldshellHubConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
