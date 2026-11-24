"""Contains all the devices supported by the Starling Home Hub integration."""

from dataclasses import dataclass
from typing import Any

from custom_components.starling_home_hub.models.api import ApiModel


@dataclass
class Device(ApiModel):
    """Class that reflects a specific device."""

    status: str
    properties: dict[str, Any]


@dataclass
class DeviceUpdate(ApiModel):
    """Class that reflects a specific device update."""

    status: str
    setStatus: dict[str, str]
