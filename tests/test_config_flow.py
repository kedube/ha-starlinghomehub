"""Tests for the config flow."""

import logging
import re
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import aiohttp_client
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starling_home_hub.const import CONF_RTSP_PASSWORD, DOMAIN
from tests.helpers import KEY, URL, register_hub, unload_all


async def test_reconfigure_does_not_log_secrets(hass, aioclient_mock, caplog):
    """Debug logging during reconfigure must not include the API key or RTSP password."""
    caplog.set_level(logging.DEBUG, logger="custom_components.starling_home_hub")
    register_hub(aioclient_mock, {})
    entry = MockConfigEntry(domain=DOMAIN, version=2,
                            data={CONF_URL: URL, CONF_API_KEY: KEY, CONF_RTSP_PASSWORD: "rtsp-secret"})
    entry.add_to_hass(hass)
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: URL, CONF_API_KEY: "new-secret-key"})
        await hass.async_block_till_done()
        for secret in (KEY, "new-secret-key", "rtsp-secret"):
            assert secret not in caplog.text
    finally:
        await unload_all(hass)


async def test_same_hub_cannot_be_added_twice(hass, aioclient_mock):
    """A second entry for the same hub URL aborts instead of duplicating every entity."""
    register_hub(aioclient_mock, {})
    MockConfigEntry(domain=DOMAIN, version=2, data={CONF_URL: URL, CONF_API_KEY: KEY}).add_to_hass(hass)
    try:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: URL, CONF_API_KEY: KEY})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
    finally:
        await unload_all(hass)


async def test_config_flow_reuses_the_shared_session(hass, aioclient_mock):
    """Failed attempts must not each create an HTTP session that lives until restart."""
    aioclient_mock.get(re.compile(r"/status\?"), status=401)
    with patch.object(aiohttp_client, "_async_create_clientsession",
                      wraps=aiohttp_client._async_create_clientsession) as spy:
        for _ in range(3):
            result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_URL: URL, CONF_API_KEY: "wrong"})
            assert result["errors"] == {"base": "auth"}
    assert spy.call_count <= 1
