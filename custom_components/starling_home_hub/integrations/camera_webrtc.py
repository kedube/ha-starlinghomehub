"""Specific code for WebRTC camera streams."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from datetime import datetime, timedelta, timezone
from webrtc_models import RTCIceCandidateInit

from homeassistant.components.camera import WebRTCAnswer, WebRTCClientConfiguration, WebRTCSendMessage
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time

from custom_components.starling_home_hub.const import LOGGER
from custom_components.starling_home_hub.coordinator import StarlingHomeHubDataUpdateCoordinator
from custom_components.starling_home_hub.entities.camera import StarlingHomeHubBaseCamera

STREAM_EXPIRATION_BUFFER = timedelta(seconds=60)


class StarlingHomeHubWebRTCCamera(StarlingHomeHubBaseCamera):
    """Starling Home Hub Web RTC Camera class (Work in progress)."""

    def __init__(
        self,
        device_id: str,
        coordinator: StarlingHomeHubDataUpdateCoordinator
    ) -> None:
        """Initialize the Camera Sensor class."""

        self._sessions: dict[str, str] = {}          # session_id -> hub streamId
        self._pending: set[str] = set()               # offers awaiting start_stream
        self._refresh_unsubs: dict[str, Callable[[], None]] = {}

        super().__init__(device_id, coordinator, "webrtc")

    async def stream_source(self) -> str | None:
        """Return stream source for the camera."""

        return None

    def _schedule_stream_refresh(self, session_id: str) -> None:
        """Schedule an extend for one session's hub stream."""

        if unsub := self._refresh_unsubs.pop(session_id, None):
            unsub()
        if session_id not in self._sessions:
            return
        self._refresh_unsubs[session_id] = async_track_point_in_utc_time(
            self.hass,
            partial(self._handle_stream_refresh, session_id),
            datetime.now(timezone.utc) + STREAM_EXPIRATION_BUFFER,
        )

    async def _handle_stream_refresh(self, session_id: str, now: datetime) -> None:
        """Extend one session's stream, dropping it if the hub refuses."""

        if (stream_id := self._sessions.get(session_id)) is None:
            return
        try:
            await self.coordinator.extend_stream(self.device_id, stream_id)
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Failed to extend stream: %s", err)
            self._sessions.pop(session_id, None)
            self._refresh_unsubs.pop(session_id, None)
            return
        self._schedule_stream_refresh(session_id)

    async def _async_stop(self, stream_id: str) -> None:
        try:
            await self.coordinator.stop_stream(self.device_id, stream_id)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Failed to stop stream: %s", err)

    async def async_will_remove_from_hass(self) -> None:
        """Stop every hub stream when unloaded."""

        for session_id in list(self._sessions):
            if unsub := self._refresh_unsubs.pop(session_id, None):
                unsub()
            await self._async_stop(self._sessions.pop(session_id))
        self._pending.clear()

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Ignore WebRTC candidates for Nest cloud based cameras."""
        return

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close one WebRTC session without touching the others."""

        self._pending.discard(session_id)
        if unsub := self._refresh_unsubs.pop(session_id, None):
            unsub()
        if (stream_id := self._sessions.pop(session_id, None)) is not None:
            self.coordinator.config_entry.async_create_background_task(
                self.hass, self._async_stop(stream_id), f"starling stop stream {stream_id}"
            )

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Start a dedicated hub stream for this session's offer."""

        self._pending.add(session_id)
        try:
            stream = await self.coordinator.start_stream(device_id=self.device_id, sdp_offer=offer_sdp)
        finally:
            still_open = session_id in self._pending
            self._pending.discard(session_id)

        if not still_open:  # closed while start_stream was in flight
            await self._async_stop(stream.streamId)
            return

        self._sessions[session_id] = stream.streamId
        self._schedule_stream_refresh(session_id)
        send_message(WebRTCAnswer(stream.answer))

    @callback
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Create data channel required for an acceptable WebRTC offer."""
        return WebRTCClientConfiguration(data_channel="dataSendChannel")
