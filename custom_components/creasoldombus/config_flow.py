"""Config flow for Creasol Test integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import serial
import serial.tools.list_ports  # import list_ports from pyserial lib
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICES, CONF_UNIQUE_ID

# from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import configFileWriteNow, creasol_dombus as dombus, creasol_dombus_const as dbc
from .const import (
    CONF_BUSNUM,
    CONF_BUSNUMENTRY,
    CONF_SAVED,
    CONF_SERIALPATH,
    CONF_SERIALPATH_MANUALLY,
    DOMAIN,
)

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

    @staticmethod
    def async_get_options_flow(config_entry):
        """Manage the CONFIGURE menu on integration list"""
        return DomBusOptionsFlowHandler(config_entry)

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


class DomBusOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Options Flow."""

    def __init__(self, config_entry):
        """Initialize DomBus options flow."""
        self.config_entry = config_entry
        # create list of installed buses
        self.busNums = []
        self.busNum = 1
        self.devID = ""
        self.cmd = ""

    async def async_step_init(self, user_input=None):
        """Manage the DomBus module configuration."""
        # create a list of active bus numbers (there may be more than 1 buses using DomBus integration)
        for bn in self.hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUM]:
            if bn != "next":
                self.busNums.append(self.hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUM][bn])
        # call the method that ask for bus and devID
        return await self.async_step_devID()

    async def async_step_devID(self, user_input=None):
        """Manage the DomBus module configuration."""
        errors = {}
        if user_input is not None:
            # options sent => check that device exists
            _LOGGER.debug("user_input = %s", str(user_input))

            if user_input["busNum"] != "" and user_input["devID"] != "":
                self.busNum = user_input["busNum"]
                self.devID = user_input["devID"]
                hwaddrport = self.devID.split(".")
                self.frameAddr = int(hwaddrport[0], 16)
                self.port = int(hwaddrport[1], 16)
                self.uniqueID = f"{self.busNum}_{self.frameAddr:04x}_{self.port:02x}"
                hub = self.hass.data[DOMAIN]["hub"][self.busNumEntry]

                # check busNum
                try:
                    self.busEntry = self.hass.data[DOMAIN][CONF_SAVED][
                        CONF_BUSNUMENTRY
                    ][self.busNum]
                except:
                    _LOGGER.warning(
                        "Invalid bus: busNum=%d, busEntry=%s",
                        self.busNum,
                        self.busEntry,
                    )
                    errors["base"] = "invalid_bus"
                    self.busNum = self.busNums[0]
                else:
                    self.busNumEntry = self.hass.data[DOMAIN][CONF_SAVED][
                        CONF_BUSNUMENTRY
                    ][self.busNum]

                    # check that device exists
                    try:
                        device = self.hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES][
                            self.busNumEntry
                        ][self.uniqueID]
                    except:
                        _LOGGER.warning("DomBus not found: uniqueID=%s", self.uniqueID)
                        _LOGGER.warning(
                            "Device = %s",
                            self.hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES][
                                self.busNumEntry
                            ][self.uniqueID],
                        )
                        errors["base"] = "dombus_not_found"
                        self.devID = ""
                    else:
                        # check parameter cmd
                        if user_input["cmd"] == "":
                            # get current configuration from device
                            _LOGGER.debug(
                                "cmd not specified: read cmd from device configuration"
                            )
                            _LOGGER.debug("device[3]=%s", device[3])
                            self.cmd = device[3][2]
                            _LOGGER.debug("self.cmd now is %s", self.cmd)

                        else:
                            # check configuration:

                            dcmd = []
                            setOpt = 0
                            setType = 0
                            setHwaddr = 0
                            setCal = 32768  # calibration offset 32768=ignore
                            setTypeName = ""
                            typeName = ""
                            setOptDefined = 0
                            setTypeDefined = 0
                            setDisableDefined = 0
                            setOptNames = ""

                            for opt in user_input["cmd"].split(","):
                                opt = opt.strip()
                                optu = opt.upper()
                                if optu in dbc.PORTTYPES:
                                    # opt="OUT_DIGITAL" or DISTANCE or ....
                                    setType = dbc.PORTTYPES[
                                        optu
                                    ]  # setType=0x2000 if DISTANCE is specified
                                    setTypeDefined = 1  # setTypeDefined=1
                                    setTypeName = optu  # setTypeName=DISTANCE
                                    typeName = dbc.PORTTYPENAME[
                                        optu
                                    ]  # typeName=Temperature
                                elif optu in dbc.PORTOPTS:
                                    if optu == "NORMAL":
                                        setOpt = 0
                                        setOptNames = ""
                                    else:
                                        setOpt = setOpt | dbc.PORTOPTS[optu]
                                        setOptNames += opt + ","
                                    setOptDefined = 1
                                elif optu[:2] == "A=":
                                    device[4]["a"] = float(opt[2:])
                                    setOptNames += opt + ","
                                elif optu[:2] == "B=":
                                    device[4]["b"] = float(opt[2:])
                                    setOptNames += opt + ","
                                elif (
                                    optu[:4] == "CAL="
                                ):  # calibration value: should be expressed as integer (e.g. temperatureOffset*10)
                                    setCal = int(float(opt[4:]) * 10)
                                elif optu[:9] == "TYPENAME=":
                                    typeName = opt[9:]
                                    setOptNames += opt + ","
                                elif (
                                    optu[:9] == "OPPOSITE="
                                ):  # Used with kWh meter to set power to 0 when the opposite counter received a pulse (if import power >0, export power must be 0, and vice versa)
                                    if (
                                        device[3][0] == dbc.PORTTYPES["IN_COUNTER"]
                                    ):  # kWh
                                        opposite = opt[
                                            9:
                                        ]  # in Domoticz was unit. In HA must be a devID
                                        (frameAddr, port) = opposite.split(".")
                                        uniqueIDnew = f"{self.busNum}_{self.frameAddr:04x}_{self.port:02x}"
                                        # verify that opposite device exists and manage it
                                        if (
                                            uniqueIDnew
                                            not in self.hass.data[DOMAIN][CONF_SAVED][
                                                CONF_DEVICES
                                            ][self.busNumEntry]
                                        ):
                                            errors["base"] = "opposite_not_found"
                                        else:
                                            deviceNew = self.hass.data[DOMAIN][
                                                CONF_SAVED
                                            ][CONF_DEVICES][self.busNumEntry][
                                                uniqueIDnew
                                            ][
                                                5
                                            ]
                                            if (
                                                deviceNew[3][0]
                                                == dbc.PORTTYPES["IN_COUNTER"]
                                            ):
                                                device[4]["opposite"] = str(opposite)
                                                setOptNames += opt + ","
                                            else:
                                                errors["base"] = "opposite_not_counter"
                                    else:
                                        error["base"] = "device_not_counter"

                                elif optu[:9] == "HWADDR=0X" and len(optu) == 13:
                                    # set hardware address
                                    hwaddr = int(optu[7:], 16)
                                    if hwaddr >= 1 and hwaddr < 65535:
                                        setHwaddr = hwaddr
                                elif optu[:8] == "DISABLE=":
                                    # TODO
                                    setOptNames += opt + ","
                                elif (
                                    optu[:6] == "DESCR="
                                    or optu[:10] == "TIMECLOSE="
                                    or optu[:9] == "TIMEOPEN="
                                ):
                                    setOptNames += opt + ","
                                elif optu[:5] == "DCMD(":
                                    # command to another dombus
                                    # TODO
                                    setOptNames += opt + ","

                            if setOptNames != "":
                                setOptNames = setOptNames[:-1]  # remove last comma ,
                                _LOGGER.info(
                                    "Config device %x.%x: type=0x%08x typeName=%s opts=0x%02x",
                                    self.frameAddr,
                                    self.port,
                                    setType,
                                    typeName,
                                    setOpt,
                                )
                                hub.txQueueAdd(
                                    0,
                                    self.frameAddr,
                                    dbc.CMD_CONFIG,
                                    5,
                                    0,
                                    self.port,
                                    [
                                        ((setType >> 8) & 0xFF),
                                        (setType & 0xFF),
                                        (setOpt >> 8),
                                        (setOpt & 0xFF),
                                    ],
                                    dbc.TX_RETRY,
                                    0,
                                )  # PORTTYPE_VERSION=1
                                hub.txQueueAdd(
                                    0,
                                    self.frameAddr,
                                    dbc.CMD_CONFIG,
                                    7,
                                    0,
                                    self.port,
                                    [
                                        ((setType >> 24) & 0xFF),
                                        ((setType >> 16) & 0xFF),
                                        ((setType >> 8) & 0xFF),
                                        (setType & 0xFF),
                                        (setOpt >> 8),
                                        (setOpt & 0xFF),
                                    ],
                                    dbc.TX_RETRY,
                                    0,
                                )  # PORTTYPE_VERSION=2

                            """
                            if (modules[frameAddr][LASTPROTOCOL]!=1):
                                #Transmit Dombus CMD config
                                dcmdnum=0
                                for i in range(0,min(len(dcmd),8)):
                                    d=dcmd[i]
                                    #note: port|=0, 0x20, 0x40, 0x60 (4 DCMD for each port)
                                    if (d[0]!=0 and d[0]<DCMD_IN_EVENTS["MAX"]):
                                        dcmdnum+=1
                                        txQueueAdd(0, frameAddr,CMD_DCMD_CONFIG, 12, 0, port|(i<<5), [ d[0],
                                            d[1]>>8, d[1]&0xff,
                                            d[2]>>8, d[2]&0xff,
                                            d[3]>>8, d[3]&0xff, d[4], d[5],
                                            d[6]>>8, d[6]&0xff ], TX_RETRY, 0)
                                if (dcmdnum==0): #DCMD not defined => transmits an empty DCMD_CONFIG 
                                    txQueueAdd(0, frameAddr, CMD_DCMD_CONFIG, 2, 0, port, [ DCMD_IN_EVENTS["NONE"] ], TX_RETRY, 0)
                            else:
                                #protocol==1 does not support DCMD_CONFIG command (too long)
                                Log(LOG_WARN,"Device "+devID+" does not support protocol #2 and DCMD commands")
                            """

                            descr = (
                                "ID="
                                + self.devID
                                + ","
                                + setTypeName
                                + ","
                                + setOptNames
                            )  # if (setTypeDefined==1) else setOptNames
                            if setTypeDefined:
                                # type was defined in the description => change TypeName, if different
                                if device[3][0] != dbc.PORTTYPES[setTypeName]:
                                    # portType has been changed
                                    _LOGGER.info(
                                        "DomBus %s: port change request, from %s to %s",
                                        self.devID,
                                        dbc.PORTTYPES_REV[device[3][0]],
                                        setTypeName,
                                    )
                                    # TODO: update or change the entity according to the new configuration
                                    # Devices[Unit].Update(TypeName=typeName, nValue=Devices[Unit].nValue, sValue=Devices[Unit].sValue, Description=str(descr))  # Update description (removing HWADDR=0x1234)

                            device[3][2] = descr  # save the new descr on entityConfig
                            if setCal != 32768:  # new calibration value
                                if setCal < 0:
                                    setCal += 65536
                                hub.txQueueAdd(
                                    0,
                                    self.frameAddr,
                                    dbc.CMD_CONFIG,
                                    4,
                                    0,
                                    self.port,
                                    [
                                        dbc.SUBCMD_CALIBRATE,
                                        ((setCal >> 8) & 0xFF),
                                        (setCal & 0xFF),
                                    ],
                                    dbc.TX_RETRY,
                                    0,
                                )

                            if setHwaddr != 0 and setHwaddr != 0xFFFF:  # hwaddr not 0
                                # send command to change hwaddr
                                hub.txQueueAdd(
                                    0,
                                    self.frameAddr,
                                    dbc.CMD_CONFIG,
                                    3,
                                    0,
                                    0,
                                    [(setHwaddr >> 8), (setHwaddr & 0xFF)],
                                    dbc.TX_RETRY,
                                    1,
                                )

                            self.cmd = user_input["cmd"]  # TODO

                            device[3][2] = self.cmd
                            # self.hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES][self.busNumEntry][self.uniqueID]=device
                            _LOGGER.debug("Now device[3]=%s", device[3])
                            _LOGGER.debug(
                                "Now self.hass....=%s",
                                self.hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES][
                                    self.busNumEntry
                                ][self.uniqueID],
                            )
                            configFileWriteNow(self.hass.data[DOMAIN][CONF_SAVED])
                            _LOGGER.warning("Configuration saved")
                            errors["base"] = "Configuration_saved"
                            self.devID = ""
                            self.cmd = ""

        # prepare options schema
        return self.async_show_form(
            step_id="devID",
            data_schema=vol.Schema(
                {
                    vol.Required("busNum", default=self.busNum): vol.In(self.busNums),
                    vol.Required("devID", default=self.devID): str,
                    vol.Optional("cmd", default=self.cmd): str,
                }
            ),
            errors=errors,
        )
