"""Switch platform."""
# import voluptuous as vol

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES
# import homeassistant.helpers.config_validation as cv

from . import creasol_dombus_const as dbc
from .const import DOMAIN, MANUFACTURER, CONF_SAVED

_LOGGER = logging.getLogger(__name__)

platform = "switch"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform."""

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add entities."""
    # save async_add_entity method for this platform, used to add new entities in the future
    if platform not in hass.data[DOMAIN]["async_add_entities"]:
        hass.data[DOMAIN]["async_add_entities"][platform] = {}
    hass.data[DOMAIN]["async_add_entities"][platform][config_entry.entry_id] = async_add_entities


class DomBusSwitch(SwitchEntity):
    """Representation of a switch."""

    def __init__(
        self,
        hub,
        unique_id,
        port_list,
        name=None,
        porttype_list=None,
        state=False,
        device_class=None,
        icon="mdi:power_outlet",
    ):
        """Initialize the switch."""
        self._hub = hub
        self._unique_id = unique_id
        self.entity_id = f"{platform}.{unique_id}"
        (self._busnum, self._protocol, self._frameAddr, self._port, self._devID, self._platform) = port_list
        self._name = name
        (self._porttype, self._portopt) = porttype_list
        self._state = state
        self._device_class = device_class
        self._icon = icon
        self._assumed = True

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
            "entry_type": "DomBus switch",
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
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def device_class(self):
        """Return device of entity."""
        return self._device_class

    @property
    def porttype(self):
        """Return the porttype."""
        return self._porttype

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug("Turn ON swith")
        self._state = True
        # self._hub.txQueueAddComplete(protocol, frameAddr, cmd, cmdLen, cmdAck, port, args, retries=1, now=1) # send command to DomBus module
        self._hub.txQueueAddComplete(0, self._frameAddr, dbc.CMD_SET, 2, 0, self._port, [1], dbc.TX_RETRY, 1)   # send command to DomBus module
        self._hub.send()    # Transmit
        self.schedule_update_ha_state()
        _LOGGER.info("Entity=%s", self)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Turn OFF swith")
        self._state = False
        self._hub.txQueueAddComplete(0, self._frameAddr, dbc.CMD_SET, 2, 0, self._port, [0], dbc.TX_RETRY, 1)   # send command to DomBus module
        self.schedule_update_ha_state()
        self._hub.send()    # Transmit
