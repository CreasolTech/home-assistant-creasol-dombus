"""Number platform."""
# import voluptuous as vol

import logging

from homeassistant.components.number import (
    NumberEntity,
)
from homeassistant.const import (
    CONF_DEVICES,
)
# import homeassistant.helpers.config_validation as cv

from . import creasol_dombus_const as dbc
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

platform = "number"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add entities."""
    devices = []
    for device_id, config in hass.data[DOMAIN][config_entry.entry_id][
        CONF_DEVICES
    ].items():
        _LOGGER.debug("new entity: device_id=%06x, config=%s", device_id, config)
        if config["porttype"] & (
            dbc.PORTTYPE_OUT_ANALOG |
            dbc.PORTTYPE_SENSOR_DISTANCE
        ):
            device = DomBusNumber(device_id, **config)
            devices.append(device)
    async_add_entities(devices, update_before_add=True)
    # check that hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"] exists:
    # it will contains a dictionary with async_add_entities function for each platform
    if "async_add_entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"] = {}
    hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"][platform] = async_add_entities


class DomBusNumber(NumberEntity):
    """Representation of Number."""

    def __init__(
        self,
        hub,
        unique_id,
        port_list,
        name=None,
        porttype_list=None,
        state=False,
        device_class=None,
        icon=None,
        # setvalue=0,
        # min_value=0,
        # max_value=100,
        # step_value=1,
    ):
        """Initialize the entity."""
        self._hub = hub
        self._unique_id = unique_id
        self.entity_id = f"{platform}.{unique_id}"
        (self._busnum, self._protocol, self._frameAddr, self._port, self._devID) = port_list
        self._name = name
        (self._porttype, self._portopt) = porttype_list
        self._state = state
        self._device_class = device_class
        self._icon = icon
        self._assumed = True
        self._value = 0         # setvalue
        self._min_value = 0     # min_value
        self._max_value = 100   # max_value
        self._step_value = 1    # step_value

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._devID)
            },
            "name": self._name,
            "manufacturer": MANUFACTURER,
            "entry_type": "DomBus number",
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self):
        """No polling needed for this entity."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def assumed_state(self):
        """Return if the state is based on assumptions."""
        return self._assumed

    @property
    def device_class(self):
        """Return device of entity."""
        return self._device_class

    @property
    def porttype(self):
        """Return the porttype."""
        return self._porttype

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._min_value

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._max_value

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
#        step = DEFAULT_STEP
#        value_range = abs(self.max_value - self.min_value)
#        if value_range != 0:
#            while value_range <= step:
#                step /= 10.0
#        return step
        return self._step_value

    @property
    def state(self) -> float:
        """Return the entity state."""
        return self._value

    @property
    def value(self) -> float:
        """Return the entity value to represent the entity state."""
        return self._value

    def set_value(self, value: float) -> None:
        """Set new value."""
        self._value = value

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        # await self.hass.async_add_executor_job(self.set_value, value)
        self._value = value
