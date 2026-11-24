"""Models for handling WebRTC stream responses."""

from dataclasses import dataclass

from custom_components.starling_home_hub.models.api import ApiModel


@dataclass
class StartStream(ApiModel):
    """Class for handling starting a WebRTC stream."""

    status: str
    answer: str
    streamId: str
    isLocal: bool


@dataclass
class StreamStatus(ApiModel):
    """Class for stream status."""

    status: str


@dataclass
class StreamExtend(ApiModel):
    """Class for extending stream."""

    status: str
