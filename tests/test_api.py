"""Tests for the API client and response parsing."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from homeassistant.exceptions import HomeAssistantError

import custom_components.starling_home_hub as integration
from custom_components.starling_home_hub.models.api.status import Status
from tests.helpers import STATUS, props, setup_entry, unload_all, register_hub


def test_integration_imports_without_async_timeout():
    """HA 2026.8 no longer ships async_timeout, so the client must not need it."""
    root = Path(integration.__file__).parents[2]
    code = ("import sys; sys.path.insert(0, sys.argv[1]); sys.modules['async_timeout'] = None; "
            "import custom_components.starling_home_hub.api")
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(root)],
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr


def test_status_permissions_are_parsed_into_a_model():
    """The nested permissions dict becomes a Permissions instance."""
    assert Status.from_dict(STATUS).permissions.read is True


async def test_unknown_response_fields_do_not_break_setup(hass, aioclient_mock):
    """New fields added by a hub firmware update are ignored, not fatal."""
    aioclient_mock.get(re.compile(r"/status\?"), json={**STATUS, "hubFirmware": "2026.43"})
    aioclient_mock.get(re.compile(r"/devices\?"),
                       json={"status": "OK", "devices": [{"id": "a"}], "cursor": None})
    aioclient_mock.get(re.compile(r"/devices/a\?"), json={
        "status": "OK", "lastUpdated": 1,
        "properties": props("a", "Alpha", "sensor", currentTemperature=20.0)})
    await setup_entry(hass)
    try:
        assert hass.states.get("sensor.room_alpha_current_temperature").state == "20.0"
    finally:
        await unload_all(hass)


async def test_malformed_update_response_is_reported_as_ha_error(hass, aioclient_mock):
    """An update response without setStatus surfaces as HomeAssistantError, not TypeError."""
    register_hub(aioclient_mock, {"a": props("a", "Plug", "outlet", isOn=False)})
    await setup_entry(hass)
    try:
        aioclient_mock.post(re.compile(r"/devices/a\?"), json={"status": "error"})
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.room_plug_is_on"}, blocking=True)
    finally:
        await unload_all(hass)
