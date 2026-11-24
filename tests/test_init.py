"""Tests for config entry migration."""

from homeassistant.const import CONF_API_KEY, CONF_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.starling_home_hub import async_migrate_entry
from custom_components.starling_home_hub.const import DOMAIN
from tests.helpers import KEY


async def test_v1_migration_only_rewrites_the_version_segment(hass):
    """Migrating to v2 changes the API path, not a hostname that happens to contain 'v1'."""
    entry = MockConfigEntry(domain=DOMAIN, version=1,
                            data={CONF_URL: "http://hubv1.lan:3080/api/connect/v1/", CONF_API_KEY: KEY})
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)
    assert entry.data[CONF_URL] == "http://hubv1.lan:3080/api/connect/v2/"
