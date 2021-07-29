"""Config flow for Creasol Test integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import serial
import serial.tools.list_ports  # import list_ports from pyserial lib
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_UNIQUE_ID

# from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_SERIALPATH, CONF_SERIALPATH_MANUALLY, DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {CONF_SERIALPATH: str}
)  # TODO: add LogLevel (NONE, ERR, WARN, INFO, DEBUG, DUMP, DUMPALL)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Creasol Test."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    def __init__(self):
        """Init ConfigFlow object."""
        self._serialpath = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [p.device for p in ports]

        if not list_of_ports:
            return (
                await self.async_step_pick_serial()
            )  # pyserial returns no serial ports => ask to enter serial port manually

        list_of_ports.append(
            CONF_SERIALPATH_MANUALLY
        )  # add to the list of ports a line that permit to enter serial port manually

        if user_input is not None:
            user_selection = user_input[CONF_SERIALPATH]
            if user_selection == CONF_SERIALPATH_MANUALLY:
                return (
                    await self.async_step_pick_serial()
                )  # ask user to enter the serial port manually

            port = ports[list_of_ports.index(user_selection)]
            # port.device=/dev/ttyUSB0

            # check that device port exists
            if os.path.exists(
                port.device
            ):  # TODO: also check that it was not open by other device
                return self.async_create_entry(
                    title=f"DomBus on {port.device}",
                    data={
                        CONF_SERIALPATH: port.device,
                        CONF_UNIQUE_ID: 1,
                    },  # TODO: UNIQUE_ID
                )

            # did not detect any serial port
            return await self.async_step_pick_serial()

        schema = vol.Schema({vol.Required(CONF_SERIALPATH): vol.In(list_of_ports)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_pick_serial(self, user_input=None):
        """Select serial port."""

        schema = {vol.Required(CONF_SERIALPATH_MANUALLY): str}
        return self.async_show_form(
            step_id="pick_serial",
            data_schema=vol.Schema(schema),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
