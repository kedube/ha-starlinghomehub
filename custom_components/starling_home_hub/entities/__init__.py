"""Contains entities that integrate directly with Home Assistant."""

from __future__ import annotations
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.starling_home_hub.const import ATTRIBUTION, DOMAIN
from custom_components.starling_home_hub.coordinator import StarlingHomeHubDataUpdateCoordinator
from custom_components.starling_home_hub.models.api.device import Device


# The raw `properties` dict of a device, as passed to entity description callables.
type DeviceType = dict[str, Any]


class StarlingHomeHubEntity(CoordinatorEntity):
    """StarlingHomeHubEntity class."""

    device_id: str

    _attr_attribution = ATTRIBUTION
    coordinator: StarlingHomeHubDataUpdateCoordinator

    def __init__(self, coordinator: StarlingHomeHubDataUpdateCoordinator) -> None:
        """Initialize."""

        super().__init__(coordinator)

        device = self.get_device()
        device_properties = device.properties
        device_id = device_properties["id"]
        model = device_properties["model"]

        manufacturer = "Unknown"
        if model.startswith("Nest"):
            manufacturer = "Google"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_properties["name"],
            model=model,
            manufacturer=manufacturer,
            suggested_area=device_properties["roomName"],
            serial_number=device_properties["serialNumber"]
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    _last_device: Device | None = None

    @property
    def available(self) -> bool:
        """Unavailable when polling fails or the hub stops reporting the device."""
        return super().available and self.device_id in self.coordinator.config_entry.runtime_data.devices

    def get_device(self) -> Device:
        """Get the device, falling back to the last-known copy if it disappeared."""
        device = self.coordinator.config_entry.runtime_data.devices.get(self.device_id)
        if device is not None:
            self._last_device = device
        return self._last_device
