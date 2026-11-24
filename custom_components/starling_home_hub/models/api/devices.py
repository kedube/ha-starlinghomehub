"""This module contains the Devices response class."""

from dataclasses import dataclass
from typing import Any

from custom_components.starling_home_hub.models.api import ApiModel


@dataclass
class Devices(ApiModel):
    """Class that reflects a devices response.

    Each entry is the raw device summary (see models.api.device.base.BaseDevice for its fields).
    """

    status: bool
    devices: list[dict[str, Any]]
