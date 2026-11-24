"""Tests for thermostat, light, and select entities."""

from homeassistant.const import Platform

from custom_components.starling_home_hub.entities.light import StarlingHomeHubLightEntity
from custom_components.starling_home_hub.entities.select import StarlingHomeHubSelectEntity
from custom_components.starling_home_hub.entities.thermostat import StarlingHomeHubThermostatEntity
from custom_components.starling_home_hub.integrations.thermostat import THERMOSTAT_PLATFORMS
from tests.helpers import make_coordinator, props

THERMOSTAT = props("t1", "Hall", "thermostat", canHeat=True, canCool=True, canHeatCool=False,
                   hvacState="off", isOnline=True)


def test_cool_mode_without_setpoint_returns_none():
    """A thermostat in cool mode with no reported setpoint has no target, not a KeyError."""
    entity = StarlingHomeHubThermostatEntity("t1", make_coordinator({"t1": {**THERMOSTAT, "hvacMode": "cool"}}))
    assert entity.target_temperature is None


async def test_hs_color_reaches_a_color_and_white_bulb():
    """Setting an HS colour works on bulbs that also support colour temperature."""
    bulb = props("l1", "Lamp", "light", isOn=True, isOnline=True, brightness=100,
                 colorTemperature=300, hue=0, saturation=0)
    coord = make_coordinator({"l1": bulb})
    await StarlingHomeHubLightEntity("l1", coord).async_turn_on(hs_color=(120.0, 50.0))
    update = coord.update_device.await_args.kwargs["update"]
    assert (update.get("hue"), update.get("saturation")) == (120.0, 50.0)


def test_sensor_select_shows_none_when_no_sensor_selected():
    """The hub's empty selection maps back to the 'None' option the entity offers."""
    thermostat = {**THERMOSTAT, "hvacMode": "heat", "sensorSelected": "", "sensorsAvailable": "Bedroom,Kitchen"}
    description = next(d for d in THERMOSTAT_PLATFORMS[Platform.SELECT] if d.key == "sensor_selected")
    entity = StarlingHomeHubSelectEntity("t1", make_coordinator({"t1": thermostat}), description)
    assert entity.options == ["None", "Bedroom", "Kitchen"]
    assert entity.current_option == "None"
