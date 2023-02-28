"""Sensor platform."""
# import voluptuous as vol

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

platform = "sensor"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add entities."""
    # save async_add_entity method for this platform, used to add new entities in the future
    if platform not in hass.data[DOMAIN]["async_add_entities"]:
        hass.data[DOMAIN]["async_add_entities"][platform] = {}
    hass.data[DOMAIN]["async_add_entities"][platform][
        config_entry.entry_id
    ] = async_add_entities


class DomBusSensor(RestoreEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        hub,
        unique_id,
        port_list,
        name=None,
        porttype_list=None,
        opts_dict=None,
    ):
        """Initialize the class."""
        self._hub = hub
        self._unique_id = unique_id
        self.entity_id = f"{platform}.{unique_id}"
        (
            self._busnum,
            self._protocol,
            self._frameAddr,
            self._port,
            self._devID,
            self._platform,
        ) = port_list
        self._name = name
        (self._porttype, self._portopt, self._descr) = porttype_list
        if opts_dict is not None:
            if "value" in opts_dict:
                self.state = opts_dict["value"]
            if "entityClass" in opts_dict:
                self.device_class = opts_dict["entityClass"]
            if "entityIcon" in opts_dict:
                self.icon = opts_dict["entityIcon"]
            if "entityUOM" in opts_dict:
                self.unit_of_measurement = opts_dict["entityUOM"]
            if "opposite" in opts_dict:
                self._opposite = opts_dict["opposite"]
        self._assumed = False
        self.last_pulses = 0
        self.power = 0

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        # Get the last save state (uses RestoreEntity class)
        state = await self.async_get_last_state()
        if state:
            # last state exists: state.state recorded as string
            if self.unit_of_measurement in [TEMP_CELSIUS, ENERGY_KILO_WATT_HOUR]:
                self.setstate(float(state.state))
            elif self.unit_of_measurement in [PERCENTAGE, ENERGY_WATT_HOUR]:
                self.setstate(int(state.state))
            else:
                self.setstate(state.state)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._devID)
            },
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "DeviceEntryType": "DomBus sensor",
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self):
        """No polling needed for this entity."""
        return False

#    @property
#    def device_class(self):
#        """Return the device class of the sensor."""
#        return self._attr_device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def porttype(self):
        """Return the porttype."""
        return self._porttype

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            return f"{self._attr_state:.3f}"  # convert to string with 3 decimal numbers
        else:
            return self._attr_state

    def setstate(self, value):
        """If value != self.state => update _state and call async_write_ha_state()."""
        if value != self.state:
            self._attr_state = value
            self.async_write_ha_state()
