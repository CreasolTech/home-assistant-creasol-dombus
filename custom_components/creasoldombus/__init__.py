"""Set up environment that mimics interaction with devices."""
import asyncio
from datetime import timedelta
import json
import logging
import re
import time

import serial_asyncio
import voluptuous as vol

# from homeassistant import config_entries
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_ENTITIES,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    TEMP_CELSIUS,
)

# import homeassistant.core as ha
from homeassistant.core import HassJob, callback
from homeassistant.helpers import event
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

# from homeassistant.helpers.entity_platform import EntityPlatform
# from homeassistant.helpers.storage import Store     # Store method to save content
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util.dt import utcnow

from . import creasol_dombus as dombus, creasol_dombus_const as dbc
from .binary_sensor import DomBusBinarySensor
from .const import (
    CONF_BUSNUM,
    CONF_BUSNUMENTRY,
    CONF_SAVED,
    CONF_SERIALPATH,
    DOMAIN,
    HEARTBEAT_INTERVAL,
)
from .light import DomBusLight
from .sensor import DomBusSensor
from .switch import DomBusSwitch

# from .number import DomBusNumber

# from homeassistant.helpers import device_registry as dr, entity_registry as er
# from homeassistant.helpers import entity_registry as er


_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    "binary_sensor",
    #    "climate",
    "light",
    # "number",
    "sensor",
    "switch",
    #    "water_heater",
]

DATA_DEVICE_REGISTER = "dombus_device_register"
SERVICE_SEND_COMMAND = "send_command"
SIGNAL_EVENT = "dombus_event"
EVENT_KEY_COMMAND = "command"
EVENT_KEY_ID = "id"

SEND_COMMAND_SCHEMA = vol.Schema(
    {vol.Required(CONF_DEVICE_ID): cv.string, vol.Required(CONF_COMMAND): cv.string}
)


class DomBusHub:
    """DomBus protocol class."""

    def __init__(self, hass, entry, loop=None):
        """Initialize."""
        self.txAckEnabled = (
            dbc.TXACK_ENABLE
        )  # DEBUG: if False, does not transmit ACKs. Used when another controller is connected to the same bus
        self.rxEnabled = False
        self.logLevel = dbc.LOG_DUMPALL  # force dumping everything
        self._hass = hass
        self.entry = entry
        # self.entry['hass'] = hass
        self._entry_id = entry.entry_id
        # init hass.data[DOMAIN] if not already exists
        configFileInit(hass, entry)
        """ hass.data[DOMAIN] structure:
            hass.data[DOMAIN][CONF_SAVED]=structure saved in non-volatile memory:
            hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUM]={entry_id1: 1, entry_id2: 2, "next": 3}  # associate numeric id to the corresponding entry_id of the component
            hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUMENTRY]={1:entry_id1, 2:entry_id2}  # associate entry_id to the numeric bus number
            hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES]={ entry_id1: [ list of entities config for bus 1 ], entry_id2: [ list of entities config for bus2 ], ...} # DomBus port configuration
            hass.data[DOMAIN][CONF_ENTITIES]={ entry_id1: [ list of entities for bus1 ], entry_id2: [ list of entities for bus2 ], ...}  # entity class pointer
            hass.data[DOMAIN]["hub"]={ entry_id1: self, entry_id2: hub2 }
        """
        if "hub" not in hass.data[DOMAIN]:
            hass.data[DOMAIN]["hub"] = {}
        hass.data[DOMAIN]["hub"][self._entry_id] = self
        self._saved_config = hass.data[DOMAIN][CONF_SAVED]
        self._entities = hass.data[DOMAIN][CONF_ENTITIES][self._entry_id]
        self._busNum = self._saved_config[CONF_BUSNUM][self._entry_id]
        self._serialpath = self.entry.data[CONF_SERIALPATH]
        self.loop = loop if loop else asyncio.get_event_loop()
        self.dombusprotocol = None
        self._connection = None
        self._connection_retry = 5
        self._connection_retry_time = 15
        self._reconnect_task = None
        self.deviceID = 0
        self.devID = 0
        self.deviceAddr = 0
        self.portsDisabled = 0
        self.portsDisabledWrite = (
            0  # number of heartbeat cycles after which portsDisabled must be saved
        )
        self.configFileWrite = (
            0  # number of heartbeat cycles after which hass.data[DOMAIN] must be saved
        )
        # txQueue[frameAddr].append([cmd,cmdLen,cmdAck,port,args,retries])
        self.txQueue = {}  # tx queue for each module
        self.modules = (
            {}
        )  # modules[frameAddr]=[lastRx, lastTx, lastSentStatus, protocol]
        self.portsDisabled = {}
        self.portsDisabledWrite = 0
        self.portsDisabledInit()  # read disabled ports for each module i.e. self.portsDisabled[0x0001]=[2,3,4,10]
        self.counterTime = (
            []
        )  # time associated to each counter: used to compute kW from energy counters
        self.Devices = {}  # TODO: to be removed
        self.protocol = 2
        self.frameAddr = 0
        self.port = 0
        self._job = HassJob(self._heartbeat)
        self._schedule_refresh()

    async def _connect(self):
        """Asyncio connection serial port."""
        # heartbeat_time = 10

        self.dombusprotocol = dombus.DomBusProtocol(self.parseFrame)
        try:
            await serial_asyncio.create_serial_connection(
                self.loop,
                lambda: self.dombusprotocol,
                self._serialpath,
                baudrate=115200,
            )
        except (ValueError, OSError, asyncio.TimeoutError) as err:
            if self._connection_retry_time <= 0:
                return
            _LOGGER.warning(
                "Could not connect to DomBus via %s: %s. Retrying in %d seconds",
                self._serialpath,
                err,
                self._connection_retry_time,
            )
            self._reconnect_task = self.loop.call_later(
                self._connection_retry_time, self._reconnect
            )
            self._connection_retry -= 1

    def _reconnect(self):
        asyncio.ensure_future(self._connect())

    def connect(self):
        """Connect to the serial port."""
        asyncio.ensure_future(self._connect())

    def portsDisabledWriteNow(self):
        """Write portsDisabled json file."""
        with open(dbc.PORTSDISABLEDFILE, "w") as fd:
            json.dump(self.portsDisabled, fd)

    def portsDisabledInit(self):
        """Read and initialize portsDisabled from json file."""
        self.portsDisabledWrite = (
            0  # time*heartbeat before writing the portsDisabled dict on json file
        )
        _LOGGER.info("portsdisabledfile=%s", dbc.PORTSDISABLEDFILE)
        try:
            fd = open(dbc.PORTSDISABLEDFILE)
        except FileNotFoundError:
            # doesn't exist?
            _LOGGER.warn(
                "Error opening file "
                + dbc.PORTSDISABLEDFILE
                + ": initializing portsDisabled...",
            )
            self.portsDisabled = {}
            self.portsDisabledWriteNow()
        else:
            self.portsDisabled = json.load(fd)
            # self.portsDisabled={0xff23=[3,4,5,11], 0xff31=[7,8]}  disabled ports, separated by colon. Port 1 can never be disabled!

    def HRstatus(
        self, hum
    ):  # return normal, comfort, dry, wet status depending by relative humdity argument
        """Return room comfort state based on relative humidity."""
        if hum < 25:
            return "2"  # dry
        elif hum > 70:
            return "3"  # wet
        elif hum >= 40 and hum <= 60:  # comfortable
            return "1"
        else:
            return "0"  # normal

    def getDeviceID(self):
        """From bus number, 16bit address + port (i.e. 0x0023, port 1), generate the corresponding deviceID ("H0023_P01"), devID ("23.1"), deviceAddr ("0x0023") and uniqueID ("1_0023_01")."""
        self.deviceID = f"H{self.frameAddr:04x}_P{self.port:02x}"
        self.devID = f"{self.frameAddr:x}.{self.port:x}"
        self.deviceAddr = f"0x{self.frameAddr:04x}"
        self.uniqueID = f"{self._busNum}_{self.frameAddr:04x}_{self.port:02x}"

    def getEntity(self):
        """Return the saved entity, if exist, corresponding to the current self.uniqueID (computed by getDeviceID)."""
        if self.uniqueID in self._entities:
            # entity class reference saved in hass.data[DOMAIN][CONF_ENTITIES][entry_id]
            return self._entities[self.uniqueID]
        else:
            return None

    def txQueueAddAck(self, cmd, cmdLen, cmdAck, args, retries=1, now=1):
        """Transmit ACK only if ACK are enabled: it's the same as txQueueAdd."""
        if self.txAckEnabled:
            self.txQueueAdd(cmd, cmdLen, cmdAck, args, retries, now)

    def txQueueAdd(self, cmd, cmdLen, cmdAck, args, retries=1, now=1):
        """Simplified function that call txQueueAddComplete() to send a frame to the module."""
        self.txQueueAddComplete(
            self.protocol,
            self.frameAddr,
            cmd,
            cmdLen,
            cmdAck,
            self.port,
            args,
            retries,
            now,
        )

    def txQueueAddComplete(
        self, protocol, frameAddr, cmd, cmdLen, cmdAck, port, args, retries=1, now=1
    ):
        """Add a command in the tx queue for the specified module (frameAddr)."""
        # if that command already exists, update it
        # cmdLen=length of data after command (port+args[])
        sec = int(time.time())
        ms = int(time.time() * 1000)
        if protocol == 0:
            # check if module already in self.modules[]
            if frameAddr in self.modules:
                protocol = self.modules[frameAddr][dbc.LASTPROTOCOL]
        if len(self.txQueue) == 0 or frameAddr not in self.txQueue:
            # create self.txQueue[self.frameAddr]
            self.txQueue[frameAddr] = [[cmd, cmdLen, cmdAck, port, args, retries]]
        else:
            found = 0
            for f in self.txQueue[frameAddr]:
                # f=[cmd,cmdlen,cmdAck,self.port,args[]]
                if (
                    f[dbc.TXQ_CMD] == cmd
                    and f[dbc.TXQ_CMDLEN] == cmdLen
                    and f[dbc.TXQ_PORT] == port
                ):
                    # command already in self.txQueue: update values
                    f[dbc.TXQ_CMDACK] = cmdAck
                    f[dbc.TXQ_ARGS] = args
                    if f[dbc.TXQ_RETRIES] < retries:
                        f[dbc.TXQ_RETRIES] = retries
                    found = 1
                    break
            if found == 0:
                self.txQueue[frameAddr].append(
                    [cmd, cmdLen, cmdAck, port, args, retries]
                )
            # txQueueRetry: don't modify it... transmit when retry time expires (maybe now or soon)
        # check that self.modules[self.frameAddr] exists
        if frameAddr not in self.modules:
            # add self.frameAddr in self.modules
            #                   lastRx  lastTx  lastSentStatus => lastTx=0 => transmit now
            self.modules[frameAddr] = [
                sec,
                ms,
                sec + 3 - dbc.PERIODIC_STATUS_INTERVAL,
                protocol,
                0,
                0,  # LASTCONFIG
            ]  # transmit output status in 3 seconds
        else:
            # self.frameAddr already in self.modules[]
            if protocol != 0:
                self.modules[frameAddr][dbc.LASTPROTOCOL] = protocol
            if now:
                self.modules[frameAddr][dbc.LASTTX] = 0  # transmit now

    def txQueueAskConfig(self):
        """Add to the txQueue the command to request device configuration."""
        self.port = 0xFF
        self.txQueueAdd(
            dbc.CMD_CONFIG, 1, 0, [], dbc.TX_RETRY
        )  # self.port=0xff to ask full configuration

    def txQueueRemove(self, cmd):
        """Remove a command from the txQueue."""
        # if txQueue[self.frameAddr] exists, remove cmd and self.port from it.
        # if cmd==255 => remove all frames for module self.frameAddr
        if len(self.txQueue) != 0 and self.frameAddr in self.txQueue:
            for f in self.txQueue[self.frameAddr][:]:
                # f=[cmd,cmdlen,cmdAck,self.port,args[],retries]
                if (cmd == 255) or (
                    f[dbc.TXQ_CMD] == cmd and f[dbc.TXQ_PORT] == self.port
                ):
                    self.txQueue[self.frameAddr].remove(f)

    def txOutputsStatus(self, Devices, frameAddr):
        """Transmit periodic status of outputs."""
        # transmit the status of outputs for the device frameAddr
        self.protocol = 0  # protocol unknown: auto detect
        for Device in Devices:
            deviceIDMask = f"H{frameAddr:04x}_P"
            d = Devices[Device]
            if d.Used == 1 and d.DeviceID[:7] == deviceIDMask:
                # device is used and matches frameAddr
                # check that this is an output
                if d.Type == dbc.PORTTYPE[dbc.PORTTYPE_OUT_DIGITAL] and re.search(
                    "(OUT_DIGITAL|OUT_RELAY_LP|OUT_DIMMER|OUT_BUZZER|OUT_ANALOG)",
                    d.Description,
                ):
                    # output! get the self.port and output state
                    self.port = int("0x" + d.DeviceID[7:11], 0)
                    if hasattr(d, "SwitchType") and d.SwitchType == 7:  # dimmer
                        if re.search("OUT_ANALOG", d.Description):
                            level = int(d.sValue) if d.nValue == 1 else 0  # 1% step
                        else:
                            level = (
                                int(int(d.sValue) / 5) if d.nValue == 1 else 0
                            )  # soft dimmer => 5% step
                        self.txQueueAdd(dbc.CMD_SET, 2, 0, [level], dbc.TX_RETRY)
                    elif hasattr(d, "SwitchType") and d.SwitchType == 18:  # selector
                        self.txQueueAdd(dbc.CMD_SET, 2, 0, [d.nValue], dbc.TX_RETRY)
                    else:
                        self.txQueueAdd(dbc.CMD_SET, 2, 0, [d.nValue], dbc.TX_RETRY)

    def registerEntity(self, entityConfig):
        """Register a new entity and save it in memory."""
        uniqueID = entityConfig[0]
        port = entityConfig[1][3]
        platform = entityConfig[1][5]
        if port > dbc.PORTS_MAX:
            return  # ignore: maybe this is a CONFIG command to ask for configuration

        if (
            len(entityConfig[3]) == 2
        ):  # add descr (configuration), that was missing in the first version
            entityConfig[3].append("")

        self._saved_config[CONF_DEVICES][self._entry_id][uniqueID] = entityConfig
        self.configFileWriteSched()  # save hass.data[DOMAIN] in 5 * HEARTBEAT_INTERVAL seconds

        # call async_add_entities for this entity and this platform, to register the new entity
        platformOk = True
        if platform == "binary_sensor":
            entity = DomBusBinarySensor(self, *entityConfig)
        elif platform == "light":
            entity = DomBusLight(self, *entityConfig)
        elif platform == "sensor":
            entity = DomBusSensor(self, *entityConfig)
        elif platform == "switch":
            entity = DomBusSwitch(self, *entityConfig)
        else:
            _LOGGER.warn("Platform %s not implemented", platform)
            platformOk = False
        if platformOk:
            _LOGGER.warn(f"Platform ok: {platform}. Now async_add_entity()")
            # store async_add_entity reference in hass.data[DOMAIN]["async_add_entities"][platform][entry.entry_ID]
            if (
                "async_add_entities" in self._hass.data[DOMAIN]
                and platform in self._hass.data[DOMAIN]["async_add_entities"]
                and self._entry_id
                in self._hass.data[DOMAIN]["async_add_entities"][platform]
            ):
                self._entities[uniqueID] = entity
                _LOGGER.info(
                    "Register new entity for platform=%s, uniqueID=%s, name=%s",
                    platform,
                    uniqueID,
                    entity.name,
                )
                self._hass.data[DOMAIN]["async_add_entities"][platform][self._entry_id](
                    (entity,), True
                )
            else:
                _LOGGER.warning(
                    "async_add_entities() not already saved in hass.data[DOMAIN][async_add_entities][%s][entry_id]",
                    platform,
                )

    def parseFrame(self, protocol, frameAddr, dstAddr, rxbuffer):
        """Get frame from DomBusProtocol and parse it."""
        if self.rxEnabled is False:
            _LOGGER.warning("Frame parsing is disabled while initializing")
            return  # frame from another controller: ignore it
        elif frameAddr == 0:
            _LOGGER.debug("Skip frame from another controller")
            return
        self.protocol = protocol
        self.frameAddr = frameAddr
        if self.frameAddr != 0xFFFF and self.frameAddr not in self.modules:
            # first time receive data from this module: ask for configuration?
            self.modules[self.frameAddr] = [
                int(time.time()),
                0,
                0,
                self.protocol,
                0,
                0,  # LASTCONFIG
            ]  # transmit now the output status
        frameIdx = 0
        frameLen = len(rxbuffer)
        while frameIdx < frameLen:
            cmd = rxbuffer[frameIdx]
            cmdAck = cmd & dbc.CMD_ACK
            cmdLen = cmd & dbc.CMD_LEN_MASK
            if self.protocol != 1:
                cmdLen *= 2
            cmd &= dbc.CMD_MASK
            portIdx = frameIdx + 1
            self.port = rxbuffer[portIdx]
            arg1 = rxbuffer[portIdx + 1] if (cmdLen >= 2) else 0
            arg2 = rxbuffer[portIdx + 2] if (cmdLen >= 3) else 0

            self.modules[self.frameAddr][dbc.LASTPROTOCOL] = self.protocol
            self.modules[self.frameAddr][dbc.LASTRX] = int(time.time())
            self.getDeviceID()
            if (
                self.deviceAddr in self.portsDisabled
                and self.port in self.portsDisabled[self.deviceAddr]
            ):
                portDisabled = 1
                entity = None
            else:
                portDisabled = 0
                entity = (
                    self.getEntity()
                )  # Return the entity corresponding to self.uniqueID computed by getDeviceID

            if entity is None:
                # entry does not exist
                if portDisabled == 0:
                    # got a frame from a unknown device, that is not disabled => ask for configuration
                    if (
                        self.port <= dbc.PORTS_MAX
                        and self.modules[self.frameAddr][dbc.LASTCONFIG] == 0
                    ):
                        # never sent Config request, or sent long time ago
                        self.modules[self.frameAddr][
                            dbc.LASTCONFIG
                        ] = 60  # timeout, decreased by _heartbeat()
                        self.txQueueAskConfig()
                    else:
                        # configuration request is not possible: transmits ACK to avoid retransmissions of the same frame
                        self.txQueueAddAck(dbc.CMD_SET, 2, dbc.CMD_ACK, [arg1])
                else:
                    # ports is disabled => send ACK anyway, to prevent useless retries
                    self.txQueueAddAck(dbc.CMD_SET, 2, dbc.CMD_ACK, [arg1])  # Tx ACK

            if cmdAck:
                # received an ack: remove cmd+arg1 from txQueue, if present
                if self.frameAddr != 0 and self.frameAddr != 0xFFFF:
                    # Received ACK from a slave module => remove cmd from txQueue
                    self.txQueueRemove(cmd)
                    self.modules[self.frameAddr][dbc.LASTRETRY] = 0

                if cmd == dbc.CMD_CONFIG and dstAddr == 0:
                    if self.port == 0xFF:
                        # 0xff VERSION PORTTYPE PORTOPT PORTCAPABILITIES PORTIMAGE PORTNAME
                        # arg1 contains the PORTTYPE_VERSION (to extend functionality in the future)
                        self.port = 1  # port starts with 1
                        portVer = (
                            arg1  # self.protocol version used to exchange information
                        )
                        frameIdx = portIdx + 2
                        entities = {}
                        for platform in PLATFORMS:
                            entities[platform] = []
                        while frameIdx < frameLen - 1:
                            # scan all ports defined in the frame
                            if portVer == 1:
                                # received configuration with version #1
                                portType = int(rxbuffer[frameIdx]) * 256 + int(
                                    rxbuffer[frameIdx + 1]
                                )
                                frameIdx += 2
                                portOpt = int(rxbuffer[frameIdx]) * 256 + int(
                                    rxbuffer[frameIdx + 1]
                                )
                                frameIdx += 2
                                # portCapabilities = int(rxbuffer[frameIdx]) * 256 + int(
                                #     rxbuffer[frameIdx + 1]
                                # )
                                frameIdx += 2
                                # portImage = int(rxbuffer[frameIdx])  # not used, ignored
                                frameIdx += 1
                            else:
                                # received configuration with version #2
                                portType = (
                                    (int(rxbuffer[frameIdx]) << 24)
                                    + (int(rxbuffer[frameIdx + 1]) << 16)
                                    + (int(rxbuffer[frameIdx + 2]) << 8)
                                    + int(rxbuffer[frameIdx + 3])
                                )
                                frameIdx += 4
                                portOpt = int(rxbuffer[frameIdx]) * 256 + int(
                                    rxbuffer[frameIdx + 1]
                                )
                                frameIdx += 2
                            portName = ""
                            for i in range(
                                0, 16
                            ):  # get the name associated to the current port
                                ch = rxbuffer[frameIdx]
                                frameIdx += 1
                                if ch == 0:
                                    break
                                else:
                                    portName += chr(ch)
                            # check if this port device already exists?
                            self.getDeviceID()
                            entity = self.getEntity()
                            if (
                                self.deviceAddr in self.portsDisabled
                                and self.port in self.portsDisabled[self.deviceAddr]
                            ):
                                portDisabled = 1
                            else:
                                portDisabled = 0

                            # check if self.frameAddr is in portsDisabled, and if the current port is disabled
                            if portDisabled == 0:
                                # current port is enabled (or new)

                                if entity:
                                    # unit found => remove TimedOut if set
                                    if self.port == 1:
                                        _LOGGER.info(
                                            "Device %s is now active again", self.devID
                                        )
                                #                                 Devices[unit].Update(nValue=Devices[unit].nValue, sValue=Devices[unit].sValue, TimedOut=0)
                                else:
                                    # port device not found, and is not disabled: create it!
                                    # portType is the numeric number provided by DOMBUS
                                    if portType not in dbc.PORT_TYPENAME:
                                        portType = (
                                            dbc.PORTTYPE_IN_DIGITAL
                                        )  # default: Digital Input
                                    descr = ""
                                    for key, value in dbc.PORTTYPES.items():
                                        if value == portType:
                                            descr += key + ","
                                            break
                                    for key, value in dbc.PORTOPTS.items():
                                        if value & portOpt:
                                            # descr=descr+key+","
                                            descr += key + ","
                                    if descr != "":
                                        descr = descr[:-1]  # remove last comma ,
                                    # create entityConfig
                                    if portType & (
                                        dbc.PORTTYPE_IN_DIGITAL | dbc.PORTTYPE_IN_AC
                                    ):
                                        # binary sensor
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "binary_sensor",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {},
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType & (
                                        dbc.PORTTYPE_OUT_DIGITAL
                                        | dbc.PORTTYPE_OUT_RELAY_LP
                                        | dbc.PORTTYPE_OUT_BUZZER
                                    ):
                                        # output
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "switch",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {},
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType == dbc.PORTTYPE_OUT_DIMMER:
                                        # dimmer output
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "light",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {
                                                value: 255,  # TODO: restore brightness stored in config
                                            },
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType == dbc.PORTTYPE_OUT_ANALOG:
                                        # 0-10V analog outputdd
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "light",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {},
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType == dbc.PORTTYPE_SENSOR_TEMP:
                                        # temperature
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "sensor",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {
                                                value: 25,  # dummy temperature
                                                SensorDeviceClass: SensorDeviceClass.TEMPERATURE,
#                                                entityIcon: None,  # icon
#                                                entityUOM: TEMP_CELSIUS,
                                            },
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType == dbc.PORTTYPE_SENSOR_HUM:
                                        # humidity
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "sensor",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {
                                                value: 50,  # dummy humidity
                                                SensorDeviceClass: SensorDeviceClass.HUMIDITY,
#                                               entityIcon: None,  # icon
#                                                entityUOM: PERCENTAGE,
                                            },
                                        ]
                                        self.registerEntity(entityConfig)
                                    elif portType == dbc.PORTTYPE_IN_COUNTER:
                                        # counter
                                        entityConfig = [
                                            self.uniqueID,
                                            [
                                                self._busNum,
                                                self.protocol,
                                                self.frameAddr,
                                                self.port,
                                                self.devID,
                                                "sensor",
                                            ],
                                            "[" + self.devID + "] " + portName,
                                            [portType, portOpt, descr],
                                            {
                                                value: 0,  # counter value TODO: restore from storage
                                                SensorDeviceClass: SensorDeviceClass.ENERGY,  # class
#                                                entityIcon: "mdi:counter",  # icon
#                                                entityUOM: ENERGY_KILO_WATT_HOUR,
                                            },
                                        ]
                                        self.registerEntity(entityConfig)
                                    else:
                                        # entityConfig cannot be added to HA
                                        _LOGGER.warning(
                                            "Entity cannot be added: devID=%s, name=%s, porttype=%s",
                                            self.devID,
                                            portName,
                                            dbc.PORT_TYPENAME[portType],
                                        )

                                    # TODO: other types....
                            self.port += 1

                    elif self.port == 0xFE:  # Version
                        if cmdLen >= 8:
                            strVersion = rxbuffer[portIdx + 1 : portIdx + 5].decode()
                            strModule = rxbuffer[
                                portIdx + 5 : portIdx + cmdLen - 1
                            ].decode()
                            _LOGGER.info(
                                "Module %s Rev.%s Addr=%x",
                                strModule,
                                strVersion,
                                self.frameAddr,
                            )
                            if self.frameAddr in self.modules:
                                self.modules[self.frameAddr][
                                    dbc.LASTSTATUS
                                ] = 0  # force transmit output status

                # TODO elif (cmd==CMD_DCMD): #decode DCMD frame to get the STATUS word?

            else:
                # cmdAck==0 => decode command from slave module
                if self.frameAddr != 0xFFFF and dstAddr == 0:
                    # Receive command from a slave module
                    self.getDeviceID()
                    if cmd == dbc.CMD_GET:
                        if (
                            self.port == 0
                        ):  # port==0 => request from module to get status of all output!  NOT USED by any module, actually
                            self.txQueueAddAck(
                                dbc.CMD_GET, 1, dbc.CMD_ACK, []
                            )  # Tx ACK
                            if self.frameAddr in self.modules:
                                self.modules[self.frameAddr][
                                    dbc.LASTSTATUS
                                ] = 0  # force transmit output status
                    elif cmd == dbc.CMD_SET:
                        # check that entity exists
                        if entity is None:
                            if portDisabled == 1:
                                # ports is disabled => send ACK anyway, to prevent useless retries
                                self.txQueueAddAck(
                                    dbc.CMD_SET, 2, dbc.CMD_ACK, [arg1]
                                )  # Tx ACK
                        else:
                            # got a frame from a well known device
                            # device_reg = dr.async_get(self._hass)
                            # device = device_reg.async_get(entity.device_id)
                            if cmdLen == 2:
                                # update device only if was changed
                                # if entity.porttype & (
                                #     dbc.PORTTYPE[dbc.PORTTYPE_OUT_DIGITAL]
                                #     | dbc.PORTTYPE[dbc.PORTTYPE_OUT_RELAY_LP]
                                # ):
                                if entity.porttype & (
                                    dbc.PORTTYPE_OUT_DIGITAL | dbc.PORTTYPE_IN_DIGITAL
                                ):
                                    if arg1 == 0:
                                        if entity.is_on:
                                            entity.turn_off()
                                    else:
                                        if entity.is_on is False:
                                            entity.turn_on()
                                elif entity.porttype == dbc.PORTTYPE_IN_COUNTER:
                                    # Counter => arg1 contains the number of pulses received in the interval
                                    if arg1 != 0:  # at least 1 pulse received
                                        if (
                                            entity.unit_of_measurement
                                            == ENERGY_KILO_WATT_HOUR
                                        ):
                                            entity.setstate(
                                                entity._state + arg1 / 1000.0
                                            )  # arg1 = number of Wh => convert to kWh
                                        else:
                                            entity.setstate(arg1)
                                        # Compute power?
                                        if entity.device_class == DEVICE_CLASS_ENERGY:
                                            ms = int(time.time() * 1000)
                                            # check that counterTime[d.Unit] exists: used to set the last time a pulse was received.
                                            # Although it's possible to save data into d.Options, it's much better to have a dict so it's possible to periodically check all counterTime
                                            msdiff = (
                                                ms - entity.last_pulses
                                            )  # elapsed time since last value
                                            if (
                                                msdiff >= 2000
                                            ):  # check that frames do not come too fast (HA busy?)
                                                # at least 2 seconds from last frame: ok
                                                entity.power = int(
                                                    arg1 * 3600000 / msdiff
                                                )
                                            entity.last_pulses = ms

                                # transmit ACK to the bus
                                self.txQueueAddAck(dbc.CMD_SET, 2, dbc.CMD_ACK, [arg1])
                            elif cmdLen == 3 or cmdLen == 4:
                                # analog value, distance, temperature or humidity
                                value = arg1 * 256 + arg2  # compute 16bit value
                                if entity.porttype == dbc.PORTTYPE_SENSOR_TEMP:
                                    temp = round(value / 10.0 - 273.1, 1)
                                    if temp > -50:
                                        entity.setstate(temp)

                                elif entity.porttype == dbc.PORTTYPE_SENSOR_HUM:
                                    hum = int(value / 10)
                                    if hum > 5:
                                        entity.setstate(hum)
                                #                                elif (d.Type==PORTTYPE[PORTTYPE_SENSOR_DISTANCE] or d.Type==PORTTYPE[PORTTYPE_IN_ANALOG]):
                                #                                    #extract A and B, if defined, to compute the right value VALUE=A*dombus_value+B
                                #                                    v=getOpt(d,"A=")
                                #                                    a=float(v) if (v!="false") else 1
                                #                                    v=getOpt(d,"B=")
                                #                                    b=float(v) if (v!="false") else 0
                                #                                    Value=a*value+b
                                #                                    if (d.sValue!=str(Value)):
                                #                                        d.Update(nValue=int(Value), sValue=str(Value))
                                #                                    #Log(LOG_DEBUG,"Value="+str(a)+"*"+str(value)+"+"+str(b)+"="+str(Value))
                                self.txQueueAddAck(
                                    dbc.CMD_SET, 3, dbc.CMD_ACK, [arg1, arg2, 0]
                                )

                                """
                                if d.Type == dbc.PORTTYPE[dbc.PORTTYPE_OUT_DIGITAL]:
                                    if (
                                        hasattr(d, "SwitchType") and d.SwitchType == 18
                                    ):  # selector
                                        d.Update(nValue=int(arg1), sValue=str(arg1))
                                        # Log(dbc.LOG_DEBUG,"devID="+devID+" d.SwitchType="+str(d.SwitchType)+" nValue="+str(arg1)+" sValue="+str(arg1))
                                    elif (
                                        hasattr(d, "SwitchType") and d.SwitchType == 7
                                    ):  # dimmer
                                        if hasattr(d, "Level") and d.Level != int(arg1):
                                            d.Update(Level=int(arg1))
                                    else:  # normal switch
                                        if (
                                            d.nValue != int(arg1)
                                            or d.sValue != stringval
                                        ):
                                            d.Update(nValue=int(arg1), sValue=stringval)
                                """

            frameIdx = frameIdx + cmdLen + 1

        self.send()  # Transmit!

    def send(self):
        """Read txQueue and generate a frame to be transmitted to one DomBus module."""
        # create frames from txQueue[], 1 for each address, and start transmitting
        # txQueue[self.frameAddr]=[[cmd, cmdLen, cmdAck, port, [arg1, arg2, arg3, ...], retries]]
        tx = 0
        sec = int(time.time())
        ms = int(time.time() * 1000)
        # scan all modules
        delmodules = []
        for frameAddr, module in self.modules.items():
            timeFromLastTx = (
                ms - module[dbc.LASTTX]
            )  # number of milliseconds since last TXed frame
            timeFromLastRx = (
                sec - module[dbc.LASTRX]
            )  # number of seconds since last RXed frame
            # timeFromLastStatus = (sec - module[dbc.LASTSTATUS])  # number of seconds since last TXed output status
            protocol = module[dbc.LASTPROTOCOL]  # 1=old protocol, 2=new protocol
            if frameAddr in self.txQueue and len(self.txQueue[frameAddr]) > 0:
                retry = module[
                    dbc.LASTRETRY
                ]  # number of retris (0,1,2,3...): used to compute the retry period
                if retry > dbc.TX_RETRY:
                    retry = dbc.TX_RETRY
                if timeFromLastTx > (dbc.TX_RETRY_TIME << (retry + 1)):
                    if protocol == 0 and retry >= dbc.TX_RETRY - 5 and (retry & 1):
                        protocol = 1  # protocol not defined: maybe it's a old device that does not transmit periodic status
                    # start txing
                    tx = 1
                    txbuffer = bytearray()
                    if protocol == 1:
                        txbuffer.append(dbc.PREAMBLE_MASTER)
                        txbuffer.append(frameAddr >> 8)
                        txbuffer.append(frameAddr & 0xFF)
                        txbuffer.append(0)
                        txbufferIndex = dbc.FRAME_HEADER
                    else:  # protocol=2 or protocol=0
                        txbuffer.append(dbc.PREAMBLE)
                        txbuffer.append(frameAddr >> 8)  # dstAddr
                        txbuffer.append(frameAddr & 0xFF)
                        txbuffer.append(0)  # master address
                        txbuffer.append(0)
                        txbuffer.append(0)  # length
                        txbufferIndex = dbc.FRAME_HEADER2
                    for txq in self.txQueue[frameAddr][
                        :
                    ]:  # iterate a copy of txQueue[frameAddr]
                        # [cmd,cmdLen,cmdAck,port,[*args]]
                        (cmd, cmdLen, cmdAck, port, args, retry) = txq
                        if txbufferIndex + cmdLen + 2 >= dbc.FRAME_LEN_MAX:
                            break  # frame must be truncated
                        if protocol == 1:
                            txbuffer.append(cmd | cmdLen | cmdAck)
                            txbufferIndex += 1
                        else:
                            txbuffer.append(
                                cmd | cmdAck | int((cmdLen + 1) / 2)
                            )  # cmdLen field is the number of cmd payload/2, so if after cmd there are 3 or 4 bytes, cmdLen field must be 2 (corresponding to 4 bytes)
                            txbufferIndex += 1
                        txbuffer.append(port)
                        txbufferIndex += 1
                        for i in range(0, cmdLen - 1):
                            txbuffer.append(args[i] & 0xFF)
                            txbufferIndex += 1

                        if protocol != 1 and (
                            cmdLen & 1
                        ):  # cmdLen is odd => add a dummy byte to get even cmdLen
                            txbuffer.append(0)
                            txbufferIndex += 1

                        # if this cmd is an ACK, or values[0]==1, remove command from the queue
                        if cmdAck or retry <= 1:
                            self.txQueue[frameAddr].remove(txq)
                        else:
                            txq[dbc.TXQ_RETRIES] = (
                                retry - 1
                            )  # command, no ack: decrement retry
                    if protocol == 1:
                        txbuffer[dbc.FRAME_LEN] = txbufferIndex - dbc.FRAME_HEADER
                    else:
                        txbuffer[dbc.FRAME_LEN2] = txbufferIndex - dbc.FRAME_HEADER2
                    module[
                        dbc.LASTRETRY
                    ] += 1  # increment RETRY to multiply the retry period * 2
                    if module[dbc.LASTRETRY] >= dbc.TX_RETRY:
                        module[dbc.LASTRETRY] = 4
                        module[
                            dbc.LASTPROTOCOL
                        ] = 0  # module does not renspond => reset protocol so both protocol 1 and 2 will be checked next time
                    txbuffer.append(self.dombusprotocol.checksum(protocol, txbuffer))
                    txbufferIndex += 1
                    self.dombusprotocol.send(txbuffer)
                    if self.logLevel >= dbc.LOG_DUMPALL or (
                        self.logLevel >= dbc.LOG_DUMP and protocol != 1
                    ):
                        self.dombusprotocol.dump(
                            protocol, txbuffer, txbufferIndex, "TX"
                        )
                    module[dbc.LASTTX] = ms

            else:  # No frame to be TXed for this frameAddr
                # check that module is active
                if timeFromLastRx > dbc.MODULE_ALIVE_TIME:
                    if protocol == 2 or dbc.PROTOCOL1_WITH_PERIODIC_TX:
                        # too long time since last RX from this module: remove it from modules
                        _LOGGER.info(
                            "Removing module %s because it's not alive", self.devID
                        )
                        delmodules.append(self.frameAddr)
                        # also remove any cmd in the txQueue
                        self.txQueueRemove(255)
                        # TODO: set device as unavailable

                    # Note: if protocol==1, maybe it uses an old firmware that does not transmit status periodically: don't remove it

        for d in delmodules:
            # remove module address of died modules (that do not answer since long time (MODULE_ALIVE_TIME))
            if d in self.modules:
                del self.modules[d]

        if (
            tx == 0
        ):  # nothing has been transmitted: send outputs status for device with older lastStatus
            olderFrameAddr = 0
            olderTime = sec
            # find the device that I sent the output status earlier
            for frameAddr, module in self.modules.items():
                if module[dbc.LASTSTATUS] < olderTime:
                    # this is the older device I sent status, till now
                    olderTime = module[dbc.LASTSTATUS]
                    olderFrameAddr = frameAddr
            # transmit only the output status of the older device, if last time I transmitted the status was at least PERIODIC_STATUS_INTERVAL seconds ago
            if sec - olderTime > dbc.PERIODIC_STATUS_INTERVAL:
                self.modules[olderFrameAddr][dbc.LASTSTATUS] = sec + (
                    olderFrameAddr & 0x000F
                )  # set current time + extra seconds to avoid all devices been refresh together
                self.txOutputsStatus(self.Devices, olderFrameAddr)

    @callback
    def _schedule_refresh(self):
        """Schedule _heartbeat() every HEARTBEAT_INTERVAL seconds."""
        event.async_track_point_in_utc_time(
            self._hass,
            self._job,  # _heartbeat()
            utcnow().replace(microsecond=0) + timedelta(seconds=HEARTBEAT_INTERVAL),
        )

    def _heartbeat(self, Devices):
        """Periodically update status and transmit."""
        # function called periodically
        # should I save portsDisabled dict on json file?
        if self.portsDisabledWrite > 0:
            self.portsDisabledWrite -= 1
            if self.portsDisabledWrite == 0:
                self.portsDisabledWriteNow()  # Write json file with list of disabled ports

        # should I write the hass.data[DOMAIN] to the config file?
        if self.configFileWrite > 0:
            self.configFileWrite -= 1
            if self.configFileWrite == 0:
                configFileWriteNow(self._saved_config)

        # Decrease dbc.LASTCONFIG counter for each module (last time we sent the CMD_CONFIG command to ask configuration)
        for frameAddr in self.modules:
            if self.modules[frameAddr][dbc.LASTCONFIG] > 0:
                self.modules[frameAddr][dbc.LASTCONFIG] -= 1

        # check counters: if configured as kWh => update decrease power in case of timeout
        delmodules = []
        for u in self.counterTime:
            # TODO
            if Devices[u].Type == 243 and Devices[u].SubType == 29:  # kWh meter
                ms = int(time.time() * 1000)
                msdiff = ms - self.counterTime[u]  # elapsed time since last value
                if msdiff > 6000:
                    # start power decay only if more than 6s since last pulse (DomBus in counter mode transmits no more than 1 frame per 2s)
                    sv = Devices[u].sValue.split(";")
                    p = int(float(sv[0]))
                    if p > 0:
                        pc = int(3600000 / msdiff)
                        if pc < p:  # power was reduced
                            sv = str(pc) + ";" + sv[1]
                            Devices[u].Update(nValue=0, sValue=sv)
            else:
                # this unit is not configured as a power meter => no need to compute power
                delmodules.append(u)
        for u in delmodules:
            del self.counterTime[u]

        # Schedule heartbeat again in HEARTBEAT_INTERVAL seconds
        if not self._hass.is_stopping:
            self._schedule_refresh()

    def configFileWriteSched(self):
        """Schedule config file writing."""
        if (
            self.configFileWrite == 0
        ):  # save hass.data[DOMAIN] in N * HEARTBEAT_INTERVAL seconds
            self.configFileWrite = 2


def configFileWriteNow(config):
    """Write config json file for DomBus buses and attached devices."""
    filename = "creasoldombus.json"
    with open(filename, "w") as fd:
        json.dump(config, fd, indent=2, sort_keys=True)


def configFileInit(hass, entry):
    """Read and initialize config json file for DomBus buses and attached devices.

    hass.data[DOMAIN] structure:
        hass.data[DOMAIN][CONF_SAVED]=structure saved in non-volatile memory:
        hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUM]={entry_id1: 1, entry_id2: 2, "next": 3}  # associate numeric id to the corresponding entry_id of the component
        hass.data[DOMAIN][CONF_SAVED][CONF_BUSNUMENTRY]={1:entry_id1, 2:entry_id2}  # associate entry_id to the numeric bus number
        hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES]={ entry_id1: [ list of entities config for bus 1 ], entry_id2: [ list of entities config for bus2 ], ...}
        hass.data[DOMAIN][CONF_ENTITIES]={ entry_id1: [ list of entities for bus1 ], entry_id2: [ list of entities for bus2 ], ...}
    """

    if DOMAIN in hass.data:
        return  # json file already loaded into hass.data[DOMAIN]

    # init hass.data[DOMAIN] if not already exists
    data = hass.data.setdefault(DOMAIN, {})
    if CONF_SAVED not in data:
        data[CONF_SAVED] = {}

    filename = "creasoldombus.json"
    try:
        fd = open(filename)
    except FileNotFoundError:
        # config file doesn't exist?
        _LOGGER.warn(
            "Error opening config file " + filename + ": initializing config dict...",
        )
    else:
        try:
            data[CONF_SAVED] = json.load(fd)
        except ValueError:
            _LOGGER.warn("Error loading json file")
    _LOGGER.debug("data[CONF_SAVED]=%s", data[CONF_SAVED])
    # check if CONF_BUSNUM dictionary exists (associate a bus number to the current bus)
    if CONF_BUSNUM not in data[CONF_SAVED]:
        # CONF_BUSNUM does not exist: set the current bus number = 1
        data[CONF_SAVED][CONF_BUSNUM] = {entry.entry_id: 1, "next": 2}
        data[CONF_SAVED][CONF_BUSNUMENTRY] = {1: entry.entry_id}
    else:
        # check the CONF_BUSNUM for this bus
        if entry.entry_id not in data[CONF_SAVED][CONF_BUSNUM]:
            # CONF_BUSNUM not set for the current bus => initialize it to the next available value
            data[CONF_SAVED][CONF_BUSNUM][entry.entry_id] = data[CONF_SAVED][
                CONF_BUSNUM
            ]["next"]
            data[CONF_SAVED][CONF_BUSNUM]["next"] += 1
            data[CONF_SAVED][CONF_BUSNUMENTRY][
                data[CONF_SAVED][CONF_BUSNUM][entry.entry_id]
            ] = entry.entry_id

        data[CONF_SAVED][CONF_BUSNUMENTRY] = {1: entry.entry_id}  # DEBUG

    if CONF_DEVICES not in data[CONF_SAVED]:
        data[CONF_SAVED][CONF_DEVICES] = {}

    # check that config has inside a dict for the current bus with the list of devices
    if entry.entry_id not in data[CONF_SAVED][CONF_DEVICES]:
        data[CONF_SAVED][CONF_DEVICES][entry.entry_id] = {}

    if CONF_DEVICES not in data[CONF_SAVED]:
        data[CONF_SAVED][CONF_DEVICES] = {}

    # check that entity structure exists
    if CONF_ENTITIES not in data:
        data[CONF_ENTITIES] = {}

    if entry.entry_id not in data[CONF_ENTITIES]:
        data[CONF_ENTITIES][entry.entry_id] = {}

    # check data["async_add_entities"]
    if "async_add_entities" not in data:
        data["async_add_entities"] = {}

    # write the structure again
    configFileWriteNow(data[CONF_SAVED])


async def async_setup_entry(hass, entry) -> bool:
    """Set up Creasol DomBus component."""

    async def async_send_command(call):
        """Send DomBus command."""
        _LOGGER.debug("DomBus command for %s", str(call.data))
        if not (await DomBusHub.send_command()):
            _LOGGER.error("Failed DomBus command for %s", str(call.data))
        else:
            async_dispatcher_send(
                hass,
                SIGNAL_EVENT,
                {
                    EVENT_KEY_ID: call.data.get(CONF_DEVICE_ID),
                    EVENT_KEY_COMMAND: call.data.get(CONF_COMMAND),
                },
            )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, async_send_command, schema=SEND_COMMAND_SCHEMA
    )

    @callback
    def event_callback(event):
        """Handle incoming DomBus events.

        DomBus events arrive as dictionaries of varying content
        depending on their type. Identify the events and distribute
        accordingly.
        """
        _LOGGER.info("event_callback: %s", event)

    hub = DomBusHub(hass, entry)
    hub.connect()

    async_dispatcher_connect(hass, SIGNAL_EVENT, event_callback)
    # load config json file into hass.data[DOMAIN]
    # configFileInit(hass, entry)
    # load entity_reg and dev_reg
    # to get an entity or device, use
    # entity = entity_reg.async_get("entity_id")
    # device = device_reg.async_get(entity.device_id)

    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_setup(entry, platform)
        # hass.async_create_task(
        #    hass.config_entries.async_forward_entry_setup(entry, platform)
        # )

    # Now register all entities saved in hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES]
    for device_id, config in hass.data[DOMAIN][CONF_SAVED][CONF_DEVICES][
        entry.entry_id
    ].items():
        hub.registerEntity(config)

    _LOGGER.info("Enable RX")
    hub.rxEnabled = True  # Enable RX when all platforms are created
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            )
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
