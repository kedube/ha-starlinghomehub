"""This module contains the CoordinatorData class."""

from dataclasses import dataclass, field
from typing import TypedDict

from custom_components.starling_home_hub.models.api.device import Device
from custom_components.starling_home_hub.models.api.status import Status


class SnapshotCacheEntry(TypedDict):
    """A cached camera snapshot and when it expires (event-loop time)."""

    snapshot: bytes
    expires: float


@dataclass
class CoordinatorData:
    """Class that houses all the coordinator runtime data required."""

    devices: dict[str, Device]
    status: Status
    device_snapshots_cache: dict[str, SnapshotCacheEntry] = field(default_factory=dict)
