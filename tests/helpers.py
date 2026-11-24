"""Helpers for building a mocked Starling Home Hub in tests."""

import re
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import CONF_API_KEY, CONF_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starling_home_hub.const import DOMAIN
from custom_components.starling_home_hub.models.api.device import Device
from custom_components.starling_home_hub.models.coordinator import CoordinatorData

URL = "http://hub.local:3080/api/connect/v2/"
KEY = "super-secret-api-key"
STATUS = {"apiVersion": 2.0, "apiReady": True, "appName": "HA",
          "permissions": {"read": True, "write": True, "camera": True}}


def props(device_id: str, name: str, category: str, **extra) -> dict:
    """Return the minimal device properties the entity base class needs."""
    return {"type": category, "category": category, "id": device_id, "name": name,
            "model": "Test", "roomId": "r1", "roomName": "Room", "structureId": "s1",
            "structureName": "Home", "serialNumber": f"SN-{device_id}", **extra}


CAM = props("cam1", "Front Door", "cam", cameraEnabled=True, isOnline=True,
            supportsWebRtcStreaming=True, rtspUrl="rtsp://192.168.1.10:8554/live")


def register_hub(aioclient_mock, devices: dict[str, dict]) -> None:
    """(Re)register hub endpoints so GET /devices returns exactly `devices`."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(re.compile(r"/status\?"), json=STATUS)
    aioclient_mock.get(re.compile(r"/devices\?"),
                       json={"status": "OK", "devices": [{"id": d} for d in devices]})
    for device_id, properties in devices.items():
        aioclient_mock.get(re.compile(rf"/devices/{device_id}\?"),
                           json={"status": "OK", "properties": properties})


def calls_to(aioclient_mock, method: str, path_suffix: str) -> list:
    """Return the mocked requests made with `method` to a path ending in `path_suffix`."""
    return [url for call_method, url, *_ in aioclient_mock.mock_calls
            if call_method.lower() == method and url.path.endswith(path_suffix)]


async def setup_entry(hass) -> MockConfigEntry:
    """Add and set up a config entry against the mocked hub."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={CONF_URL: URL, CONF_API_KEY: KEY})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def unload_all(hass) -> None:
    """Unload every entry so no coordinator timers linger past the test."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def make_coordinator(devices: dict[str, dict]) -> MagicMock:
    """Return a stand-in coordinator for entity-level unit tests."""
    coord = MagicMock()
    coord.last_update_success = True
    coord.config_entry.runtime_data = CoordinatorData(
        devices={k: Device(status="OK", properties=v) for k, v in devices.items()}, status=None)
    coord.config_entry.async_create_background_task = (
        lambda hass, coro, name, **kw: hass.async_create_task(coro))
    for name in ("update_device", "start_stream", "stop_stream", "extend_stream"):
        setattr(coord, name, AsyncMock())
    return coord
