"""Tests for polling, device updates, and availability."""

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from homeassistant.const import CONF_API_KEY, CONF_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starling_home_hub.const import DOMAIN
from custom_components.starling_home_hub.coordinator import StarlingHomeHubDataUpdateCoordinator
from custom_components.starling_home_hub.models.api.device import Device
from tests.helpers import CAM, KEY, URL, calls_to, props, register_hub, setup_entry, unload_all


async def test_setup_polls_the_hub_once(hass, aioclient_mock):
    """Adding entities must not force a second full poll right after the first refresh."""
    register_hub(aioclient_mock, {"a": props("a", "Alpha", "sensor", currentTemperature=20.0)})
    await setup_entry(hass)
    try:
        assert len(calls_to(aioclient_mock, "get", "/devices")) == 1
    finally:
        await unload_all(hass)


async def test_device_details_are_fetched_concurrently_with_a_cap(hass):
    """Per-device requests run in parallel, but never more than the hub limit at once."""
    from custom_components.starling_home_hub.coordinator import MAX_CONCURRENT_DEVICE_REQUESTS

    in_flight = max_in_flight = 0

    async def get_device(device_id):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        in_flight -= 1
        return Device(status="OK", properties=props(device_id, device_id, "sensor"))

    client = MagicMock()
    client.async_get_devices = AsyncMock(return_value=[{"id": f"d{i}"} for i in range(10)])
    client.async_get_status = AsyncMock(return_value=None)
    client.async_get_device = AsyncMock(side_effect=get_device)
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={CONF_URL: URL, CONF_API_KEY: KEY})
    entry.add_to_hass(hass)
    coordinator = StarlingHomeHubDataUpdateCoordinator(hass=hass, client=client, config_entry=entry)

    data = await coordinator.fetch_data()

    assert len(data.devices) == 10
    assert 1 < max_in_flight <= MAX_CONCURRENT_DEVICE_REQUESTS


async def test_snapshot_cache_survives_a_poll(hass, aioclient_mock):
    """A poll must not throw away a snapshot that is still within its 10 s lifetime."""
    register_hub(aioclient_mock, {"cam1": CAM})
    aioclient_mock.get(re.compile(r"/devices/cam1/snapshot\?"), content=b"jpeg")
    entry = await setup_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    try:
        assert await coordinator.get_snapshot("cam1") == b"jpeg"
        await coordinator.async_refresh()
        assert await coordinator.get_snapshot("cam1") == b"jpeg"
        assert len(calls_to(aioclient_mock, "get", "/snapshot")) == 1
    finally:
        await unload_all(hass)


async def test_removed_device_becomes_unavailable(hass, aioclient_mock):
    """A device the hub stops reporting goes unavailable; other devices keep updating."""
    register_hub(aioclient_mock, {
        "a": props("a", "Alpha", "sensor", currentTemperature=20.0),
        "b": props("b", "Beta", "sensor", currentTemperature=20.0),
    })
    entry = await setup_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    try:
        register_hub(aioclient_mock, {"b": props("b", "Beta", "sensor", currentTemperature=25.0)})
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.room_beta_current_temperature").state == "25.0"
        assert hass.states.get("sensor.room_alpha_current_temperature").state == "unavailable"
    finally:
        await unload_all(hass)


async def test_failed_refresh_after_successful_write_does_not_fail_command(hass, aioclient_mock):
    """If the write lands but the follow-up poll fails, the command still succeeds."""
    register_hub(aioclient_mock, {"a": props("a", "Plug", "outlet", isOn=False)})
    await setup_entry(hass)
    try:
        aioclient_mock.clear_requests()
        aioclient_mock.post(re.compile(r"/devices/a\?"), json={"status": "OK", "setStatus": {"isOn": "OK"}})
        aioclient_mock.get(re.compile(r"/devices"), exc=aiohttp.ClientError("hub hiccup"))
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.room_plug_is_on"}, blocking=True)
        assert len(calls_to(aioclient_mock, "post", "/devices/a")) == 1
    finally:
        await unload_all(hass)
