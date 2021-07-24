"""Switch platform."""
# import voluptuous as vol

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES

from . import creasol_dombus_const as dbc
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

platform = "switch"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up switches."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the switch entities."""
    devices = []
    _LOGGER.info("Setup switch entities...")
    for device_id, config in hass.data[DOMAIN][config_entry.entry_id][
        CONF_DEVICES
    ].items():
        _LOGGER.info("new entity: device_id=%06x, config=%s", device_id, config)
        if config["porttype"] == dbc.PORTTYPE_OUT_RELAY_LP or (
            config["porttype"] == dbc.PORTTYPE_OUT_DIGITAL
        ):
            device = DomBusSwitch(device_id, **config)
            devices.append(device)
    async_add_entities(devices, update_before_add=True)
    _LOGGER.info(
        "Store async_add_entity in hass.data[DOMAIN][config_entry.entry_id][async_add_entity]"
    )
    # check that hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"] exists:
    # it will contains a dictionary with async_add_entities function for each platform
    if "async_add_entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"] = {}
    hass.data[DOMAIN][config_entry.entry_id]["async_add_entities"][platform] = async_add_entities


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
        (self._busnum, self._protocol, self._frameAddr, self._port, self._devID) = port_list
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
