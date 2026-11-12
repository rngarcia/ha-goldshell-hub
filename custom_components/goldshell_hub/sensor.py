"""Sensor platform for Goldshell Hub."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoldshellHubConfigEntry
from .const import DOMAIN, MANUFACTURER, STATUS_MAP
from .coordinator import GoldshellHubCoordinator

RATE_UNIT = "MH/s"  # the hub reports nowrate/avgrate in MH/s (verified on the Byte)


def _num(value: Any) -> float | None:
    """Extract a float from a number or a string like ``"59.1 °C"``."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def _status(value: Any) -> str | None:
    """Map a numeric status code to a label."""
    try:
        return STATUS_MAP.get(int(value), "unknown")
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class GoldshellSensorDescription(SensorEntityDescription):
    """Describes a Goldshell sensor and how to read its value."""

    value_fn: Callable[[dict[str, Any]], Any]


MACHINE_SENSORS: tuple[GoldshellSensorDescription, ...] = (
    GoldshellSensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda m: _status(m.get("status")),
    ),
    GoldshellSensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.get("sv"),
    ),
    GoldshellSensorDescription(
        key="power_mode",
        translation_key="power_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: m.get("power_mode"),
    ),
    GoldshellSensorDescription(
        key="uptime",
        translation_key="uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m: _num(m.get("duration")),
    ),
)

BOARD_SENSORS: tuple[GoldshellSensorDescription, ...] = (
    GoldshellSensorDescription(
        key="hashrate",
        translation_key="hashrate",
        native_unit_of_measurement=RATE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda b: _num(b.get("nowrate")),
    ),
    GoldshellSensorDescription(
        key="hashrate_avg",
        translation_key="hashrate_avg",
        native_unit_of_measurement=RATE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda b: _num(b.get("avgrate")),
    ),
    GoldshellSensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda b: _num(b.get("temperature")),
    ),
    GoldshellSensorDescription(
        key="fan",
        translation_key="fan",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda b: _num(b.get("fan")),
    ),
    GoldshellSensorDescription(
        key="board_status",
        translation_key="board_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda b: _status(b.get("status")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoldshellHubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for every machine and board on the account."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for mac, machine in coordinator.data.items():
        for desc in MACHINE_SENSORS:
            entities.append(GoldshellMachineSensor(coordinator, mac, desc))
        for board in machine.get("boards", []):
            location = board.get("location")
            for desc in BOARD_SENSORS:
                entities.append(
                    GoldshellBoardSensor(coordinator, mac, location, desc)
                )

    async_add_entities(entities)


class _GoldshellBase(CoordinatorEntity[GoldshellHubCoordinator], SensorEntity):
    """Shared device/availability plumbing."""

    entity_description: GoldshellSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: GoldshellHubCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac

    @property
    def _machine(self) -> dict[str, Any] | None:
        return self.coordinator.data.get(self._mac)

    @property
    def device_info(self) -> DeviceInfo:
        machine = self._machine or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=machine.get("dev_name") or self._mac,
            manufacturer=MANUFACTURER,
            model=machine.get("kind") or machine.get("coin"),
            sw_version=machine.get("sv"),
            connections=(
                {(CONNECTION_NETWORK_MAC, format_mac(self._mac))}
                if ":" in self._mac
                else set()
            ),
        )

    @property
    def available(self) -> bool:
        return super().available and self._machine is not None


class GoldshellMachineSensor(_GoldshellBase):
    """A machine-level sensor."""

    def __init__(
        self,
        coordinator: GoldshellHubCoordinator,
        mac: str,
        description: GoldshellSensorDescription,
    ) -> None:
        super().__init__(coordinator, mac)
        self.entity_description = description
        self._attr_unique_id = f"{mac}_{description.key}"

    @property
    def native_value(self) -> Any:
        if self._machine is None:
            return None
        return self.entity_description.value_fn(self._machine)


class GoldshellBoardSensor(_GoldshellBase):
    """A per-board (hashboard) sensor."""

    def __init__(
        self,
        coordinator: GoldshellHubCoordinator,
        mac: str,
        location: Any,
        description: GoldshellSensorDescription,
    ) -> None:
        super().__init__(coordinator, mac)
        self._location = location
        self.entity_description = description
        self._attr_unique_id = f"{mac}_{location}_{description.key}"
        coin = self._board.get("coin") if self._board else None
        # Prefix the friendly name with the board's coin so the two cards are
        # distinguishable, e.g. "ALPH Hashrate" / "ALEO Temperature".
        self._attr_translation_placeholders = {"coin": coin or f"board {location}"}

    @property
    def _board(self) -> dict[str, Any] | None:
        machine = self._machine
        if not machine:
            return None
        for board in machine.get("boards", []):
            if board.get("location") == self._location:
                return board
        return None

    @property
    def available(self) -> bool:
        return super().available and self._board is not None

    @property
    def native_value(self) -> Any:
        board = self._board
        if board is None:
            return None
        return self.entity_description.value_fn(board)
