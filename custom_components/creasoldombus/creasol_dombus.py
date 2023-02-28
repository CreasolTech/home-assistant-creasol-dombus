"""Library to interface dombus modules (RS485 bus)."""

import asyncio
import logging

from . import creasol_dombus_const as dbc

_LOGGER = logging.getLogger(__name__)


class DomBusProtocol(asyncio.Protocol):
    """Class that manages data exchanged with DomBus modules."""

    def __init__(self, parseFrame):
        """Init the DomBusProtocol object."""
        self.logLevel = (
            dbc.LOG_DUMPALL  # default log level: will be initialized by onStart()
        )
        self.transport = None
        self.rxbuffer = bytearray()  # serial rx buffer
        self.rxbufferindex = 0
        self.txbuffer = bytearray()  # serial tx buffer
        self._parseFrame = parseFrame

    def connection_made(self, transport):
        """Call when serial connection is made."""
        self.transport = transport
        _LOGGER.debug("Serial port opened: %s", transport)

    def data_received(self, data):
        """Call serial_async when data is received."""
        self.rxbuffer += (
            data  # Simply add new data to the current self.rxbuffer[], and call decode
        )
        self.decode()

    def send(self, txbuffer):
        """Just transmits the frame prepared into txbuffer."""
        self.transport.write(txbuffer)
        # _LOGGER.debug("TX disabled by send()")

    def connection_lost(self, exc):
        """Call when serial connection is lost."""
        _LOGGER.error("Serial port closed")
        asyncio.get_event_loop().stop()

    def checksum(self, protocol, buffer):
        """Compute frame checksum."""
        self.checksumValue = 0
        if protocol == 1:
            length = buffer[dbc.FRAME_LEN] + dbc.FRAME_HEADER
        else:
            length = buffer[dbc.FRAME_LEN2] + dbc.FRAME_HEADER2
        for i in range(0, length):
            self.checksumValue += buffer[i]
        self.checksumValue &= 0xFF
        return self.checksumValue

    def dump(self, protocol, buffer, frameLen, direction):
        """Write frame content to the log."""
        # buffer=frame buffer
        # frameLen=length of frame in bytes
        # direction="RX" or "TX"
        if protocol == 1:
            f = "P:1 "
            fl = (
                frameLen if (frameLen <= len(buffer)) else len(buffer)
            )  # manage the case that frame is received only partially
            for i in range(0, fl):
                f += "%.2x " % int(buffer[i])
            _LOGGER.debug(direction + " frame: " + f)
        elif self.logLevel >= dbc.LOG_INFO:
            f = "P:2 "
            f += "%.2x " % int(buffer[0])
            f += "%.4x " % (int(buffer[3]) * 256 + int(buffer[4]))
            f += "-> "
            f += "%.4x " % (int(buffer[1]) * 256 + int(buffer[2]))
            f += "%.2d " % int(buffer[5])  # length
            i = dbc.FRAME_HEADER2
            while i < frameLen - 1:
                # TODO: write SET 01 00 SET 02 01 SET 03 0a SET
                # TODO: write CFG 02 FF
                cmd = int(buffer[i]) & dbc.CMD_MASK
                cmdAck = int(buffer[i]) & dbc.CMD_ACK
                cmdLen = (int(buffer[i]) & dbc.CMD_LEN_MASK) * 2
                if cmdLen == 0:
                    cmdLen = 2  # minimum cmdLen
                if cmdAck:
                    f += "A-"
                if cmd == dbc.CMD_CONFIG:
                    f += "CFG "
                    if cmdAck and int(buffer[i + 1] == 0xFF):
                        # whole port configuration => cmdLen without any sense
                        cmdLen = (
                            frameLen - dbc.FRAME_HEADER2 - 2
                        )  # force cmdLen to the whole frame
                elif cmd == dbc.CMD_SET:
                    f += "SET "
                elif cmd == dbc.CMD_GET:
                    f += "GET "
                elif cmd == dbc.CMD_DCMD_CONFIG:
                    f += "DCMDCFG "
                elif cmd == dbc.CMD_DCMD:
                    f += "DCMD "
                else:
                    f += "%.2x " % int(buffer[i])
                i += 1

                for j in range(0, cmdLen):
                    if (i+j)>=frameLen: break
                    f += "%.2x " % int(buffer[i + j])
                f += "| "
                i += cmdLen
            f += "%.2x " % int(buffer[i])  # checksum
            if (
                cmd == dbc.CMD_DCMD
            ):  # log DCMD command with priority INFO, so it's possible to monitor traffic between DomBus self.modules
                _LOGGER.info(direction + " frame: " + f)
            else:
                _LOGGER.debug(direction + " frame: " + f)
        return

    def decode(self):
        """Decode data from self.rxbuffer."""
        # align self.rxbuffer[] so it starts with a preamble
        while len(self.rxbuffer) >= dbc.FRAME_LEN_MIN and (
            self.rxbuffer[0] != dbc.PREAMBLE_DEVICE and self.rxbuffer[0] != dbc.PREAMBLE
        ):
            self.rxbuffer.pop(0)
        if len(self.rxbuffer) < dbc.FRAME_LEN_MIN:
            return
        frameError = 1
        # decode frame RXed from serial port
        # frame structure was explained above, in the comments
        if self.rxbuffer[0] == dbc.PREAMBLE_DEVICE:
            # protocol 1.0 (short version, without sender address)
            protocol = 1
            frameLen = int(self.rxbuffer[dbc.FRAME_LEN]) + dbc.FRAME_HEADER + 1
            # _LOGGER.debug("Rx frame with protocol=%d, frameLen=%d", protocol, frameLen)
            if frameLen < dbc.FRAME_LEN_MIN:
                frameError = 4  # invalid frame length
            elif len(self.rxbuffer) >= frameLen:
                # length of frame is in the range
                # compute and compare checksum
                self.checksum(protocol, self.rxbuffer)
                if self.logLevel >= dbc.LOG_DUMPALL:
                    self.dump(protocol, self.rxbuffer, frameLen, "RX")
                if self.checksumValue == self.rxbuffer[frameLen - 1]:
                    # frame checksum is ok
                    frameAddr = int(self.rxbuffer[1]) * 256 + int(self.rxbuffer[2])
                    frameIdx = dbc.FRAME_HEADER
                    dstAddr = 0  # Protocol 1 does not have destination address => force dstAddr = 0
                    frameError = 0
                else:
                    frameError = 2  # 2=checksum error
            else:
                frameError = 3  # 3=insufficient data
        elif self.rxbuffer[0] == dbc.PREAMBLE:
            protocol = 2
            frameLen = int(self.rxbuffer[dbc.FRAME_LEN2]) + dbc.FRAME_HEADER2 + 1
            # _LOGGER.debug("Rx frame with protocol=%d, frameLen=%d", protocol, frameLen)
            if frameLen < dbc.FRAME_LEN_MIN2:
                frameError = 4  # invalid frame length
            elif len(self.rxbuffer) >= frameLen:
                # length of frame is in the range
                # compute and compare checksum
                self.checksum(protocol, self.rxbuffer)
                if self.logLevel >= dbc.LOG_DUMP:
                    self.dump(protocol, self.rxbuffer, frameLen, "RX")
                if self.checksumValue == self.rxbuffer[frameLen - 1]:
                    # frame checksum is ok
                    frameAddr = int(self.rxbuffer[3]) * 256 + int(
                        self.rxbuffer[4]
                    )  # sender
                    dstAddr = int(self.rxbuffer[1]) * 256 + int(
                        self.rxbuffer[2]
                    )  # destination
                    frameIdx = dbc.FRAME_HEADER2
                    # broadcast or txQueue exists or txQueue just created
                    frameError = 0
                else:
                    frameError = 2  # 2=checksum error
            else:
                frameError = 3  # 3=insufficient data

        if frameError == 0:  # parse frame
            if frameAddr != 0xFFFF and dstAddr == 0:
                # Receive command from a slave module
                self._parseFrame(
                    protocol, frameAddr, dstAddr, self.rxbuffer[frameIdx : frameLen - 1]
                )

            # remove current frame from buffer
            del self.rxbuffer[0:frameLen]
        else:
            if frameError != 3:
                # 3 => insufficient data into rxbuffer: wait for frame completing....
                # 1, 2 or 4 => erase the first byte of buffer and seek for new preamble
                # checksum error or frame error
                if frameError == 2:
                    _LOGGER.debug("Checksum error")
                else:
                    _LOGGER.debug("frameError = " + str(frameError))
                # Erase the first byte of rxbuffer, so the method will look for the next preamble
                del self.rxbuffer[0]
        return
