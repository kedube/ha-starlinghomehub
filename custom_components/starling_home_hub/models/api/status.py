"""Models for the status response from the Starling Home Hub API."""

from dataclasses import dataclass
from typing import Any, Self

from custom_components.starling_home_hub.models.api import ApiModel


@dataclass
class Permissions(ApiModel):
    """Class that reflects permissions response."""

    read: bool
    write: bool
    camera: bool


@dataclass
class Status(ApiModel):
    """Class that reflects a status response."""

    apiVersion: float
    apiReady: bool
    appName: str
    permissions: Permissions

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create a Status, including its nested Permissions."""
        status = super().from_dict(data)
        if isinstance(status.permissions, dict):
            status.permissions = Permissions.from_dict(status.permissions)
        return status
