"""Some constants used by DomBus protocol."""

#if 1, when a module does not transmit for more than 15 minutes (MODULE_ALIVE_TIME), it will appear in red (TimedOut)
PROTOCOL1_WITH_PERIODIC_TX=0    # set to 1 if all existing modules transmit their status periodically (oldest modules with protocol 1 did not)

PORTSDISABLEDFILE = "creasoldombus_%d_portsDisabled.json"
PORTS_MAX = 32

# some constants
FRAME_LEN_MIN = 6
FRAME_LEN_MIN2 = 9  # Min length of frame for protocol 2
FRAME_LEN_MAX = 31  # max length for TX (devices cannot handle long frames)
FRAME_LEN = 3
FRAME_LEN2 = 5
FRAME_HEADER = 4
FRAME_HEADER2 = 6
PREAMBLE_MASTER = 0x5A
PREAMBLE_DEVICE = 0xDA
PREAMBLE = 0x3A  # Preamble for protocol 2
CMD_LEN_MASK = 0x07
CMD_MASK = 0xF0
CMD_ACK = 0x08

TX_RETRY = 10  # max number of retries
TX_RETRY_TIME = 80  # ms: retry every TX_RETRY_TIME * 2^retry
PERIODIC_STATUS_INTERVAL = (
    300  # seconds: refresh output status to device every 5 minutes
)
MODULE_ALIVE_TIME = 900  # if no frame is received in this time, module is considered dead (and periodic output status will not be transmitted)

CMD_CONFIG = 0x00  # Config port
CMD_GET = 0x10  # Get status
CMD_SET = 0x20  # Set outputs/values
CMD_DCMD_CONFIG = 0xE0  # Send DCMD configuration
CMD_DCMD = 0xF0  # Receive DCMD command from Dombus

SUBCMD_CALIBRATE = 0x00

PORTTYPE_DISABLED = 0x0000  # port not used
PORTTYPE_OUT_DIGITAL = 0x0002  # digital, opto or relay output
PORTTYPE_OUT_RELAY_LP = 0x0004  # relay output with lowpower PWM
PORTTYPE_OUT_LEDSTATUS = 0x0008  # output used as led status
PORTTYPE_OUT_DIMMER = 0x0010  # dimmer output, 0-100%
PORTTYPE_OUT_BUZZER = (
    0x0020  # buzzer outputs (2 ports used as buzzer output, in push-pull)
)
PORTTYPE_IN_AC = 0x0040  # input AC 50Hz (with optocoupler)
PORTTYPE_IN_DIGITAL = 0x0080  # input digital
PORTTYPE_IN_ANALOG = 0x0100  # input analog (ADC)
PORTTYPE_IN_TWINBUTTON = (
    0x0200  # 2 buttons connected to a single input through a resistor
)
PORTTYPE_IN_COUNTER = 0x0400  # input pulses that increase a counter (incremental)
PORTTYPE_1WIRE = 0x1000  # 1 wire
PORTTYPE_SENSOR_DISTANCE = (
    0x2000  # distance measurement (send a pulse and measure echo delay)
)
PORTTYPE_SENSOR_TEMP = 0x4000  # Temperature
PORTTYPE_SENSOR_HUM = 0x8000  # Relative Humidity
PORTTYPE_SENSOR_TEMP_HUM = 0xC000  # Temp+Hum
PORTTYPE_OUT_BLIND = 0x01000000  # Blind output, close command (next port of DomBus device will be automatically used as Blind output, open command)
PORTTYPE_OUT_ANALOG = 0x02000000  # 0-10V output, 1% step, 0-100

PORTOPT_NONE = 0x0000  # No options
PORTOPT_INVERTED = 0x0001  # Logical inverted: MUST BE 1

PORTTYPE = {
    PORTTYPE_OUT_DIGITAL: 244,
    PORTTYPE_OUT_RELAY_LP: 244,
    PORTTYPE_OUT_LEDSTATUS: 244,
    PORTTYPE_OUT_DIMMER: 244,
    PORTTYPE_OUT_BUZZER: 244,
    PORTTYPE_IN_AC: 244,
    PORTTYPE_IN_DIGITAL: 244,
    PORTTYPE_IN_ANALOG: 244,
    PORTTYPE_IN_TWINBUTTON: 244,
    PORTTYPE_IN_COUNTER: 243,
    PORTTYPE_SENSOR_HUM: 81,
    PORTTYPE_SENSOR_TEMP: 80,
    PORTTYPE_SENSOR_TEMP_HUM: 82,
    PORTTYPE_SENSOR_DISTANCE: 243,
    PORTTYPE_OUT_BLIND: 244,
    PORTTYPE_OUT_ANALOG: 244,
}


PORT_TYPENAME = {
    PORTTYPE_OUT_DIGITAL: "Switch",
    PORTTYPE_OUT_RELAY_LP: "Switch",
    PORTTYPE_OUT_LEDSTATUS: "Switch",
    PORTTYPE_OUT_DIMMER: "Dimmer",
    PORTTYPE_OUT_BUZZER: "Switch",
    PORTTYPE_IN_AC: "Switch",
    PORTTYPE_IN_DIGITAL: "Switch",
    PORTTYPE_IN_ANALOG: "Voltage",
    PORTTYPE_IN_TWINBUTTON: "Selector Switch",
    PORTTYPE_IN_COUNTER: "Counter Incremental",
    PORTTYPE_SENSOR_HUM: "Humidity",
    PORTTYPE_SENSOR_TEMP: "Temperature",
    PORTTYPE_SENSOR_TEMP_HUM: "Temp+Hum",
    PORTTYPE_SENSOR_DISTANCE: "Distance",
    PORTTYPE_OUT_BLIND: "Switch",
    PORTTYPE_OUT_ANALOG: "Dimmer",
}

PORTTYPES = {
    "DISABLED": 0x0000,  # port not used
    "OUT_DIGITAL": 0x0002,  # relay output
    "OUT_RELAY_LP": 0x0004,  # relay output
    "OUT_LEDSTATUS": 0x0008,  # output used as led status
    "OUT_DIMMER": 0x0010,  # dimmer output
    "OUT_BUZZER": 0x0020,  # buzzer output (2 ports, push-pull)
    "IN_AC": 0x0040,  # input AC 50Hz (with optocoupler)
    "IN_DIGITAL": 0x0080,  # input digital
    "IN_ANALOG": 0x0100,  # input analog (ADC)
    "IN_TWINBUTTON": 0x0200,  # 2 buttons connected to a single input through a resistor
    "IN_COUNTER": 0x0400,  # pulse counter
    "DISTANCE": 0x2000,  # measure distance in mm
    "TEMPERATURE": 0x4000,  # temperature
    "HUMIDITY": 0x8000,  # relative humidity
    "TEMP+HUM": 0xC000,  # temp+hum
    "OUT_BLIND": 0x01000000,  # blind with up/down/stop command
    "OUT_ANALOG": 0x02000000,  # 0-10V output, 0-100, 1% step
}

PORTOPTS = {
    "NORMAL": 0x0000,  # no options defined
    "INVERTED": 0x0001,  # input or output is inverted (logic 1 means the corresponding GPIO is at GND
}

PORTTYPENAME = {  # Used to set the device TypeName
    "DISABLED": "Switch",
    "OUT_DIGITAL": "Switch",
    "OUT_RELAY_LP": "Switch",
    "OUT_LEDSTATUS": "Switch",  # output used as led status
    "OUT_DIMMER": "Dimmer",
    "OUT_BUZZER": "Switch",
    "IN_AC": "Switch",
    "IN_DIGITAL": "Switch",
    "IN_ANALOG": "Voltage",
    "IN_TWINBUTTON": "Selector Switch",
    "IN_COUNTER": "Counter Incremental",
    "HUMIDITY": "Humidity",
    "TEMPERATURE": "Temperature",
    "TEMP+HUM": "Temp+Hum",
    "DISTANCE": "Distance",
    #        "OUT_BLIND":"Venetian Blinds EU", #not available in domoticz yet. hardware/plugins/PythonObjects.cpp must be updated!
    "OUT_BLIND": "Switch",
    "OUT_ANALOG": "Dimmer",
}

DCMD_IN_EVENTS = {
    "NONE": 0,
    "OFF": 1,
    "ON": 2,
    "PULSE": 3,  # short pulse
    "PULSE1": 4,  # 1s pulse
    "PULSE2": 5,  # 2s pulse
    "PULSE4": 6,  # 4s pulse
    "DIMMER": 7,  # Dimming control
    "VALUE": 8,  # value (sensor, voltage, ...)
    "ONUP": 9,  # Twinbutton UP
    "PULSEUP": 10,
    "PULSEUP1": 11,
    "PULSEUP2": 12,
    "PULSEUP4": 13,
    "MAX": 14,  # max number of events
}

DCMD_OUT_CMDS = {
    "NONE": 0,
    "OFF": 1,  # Turn off output
    "ON": 2,  # turn ON output
    "TOGGLE": 3,  # toggle output ON -> OFF -> ON -> ....
    "DIMMER": 4,  # set value
    "DOWN": 5,  # Blind DOWN
    "UP": 6,  # Blind UP
    "MAX": 7,  # Max number of commands
}

frameLen = 0

LASTRX = 0  # first field in modules[]
LASTTX = 1  # second field in modules[]
LASTSTATUS = 2  # third field in modules[]
LASTPROTOCOL = 3  # forth field in modules[]
LASTRETRY = (
    4  # fifth field in modules[]: number of retries (used to compute the tx period)
)
LASTCONFIG = (
    5  # used to limit the configuration request to modules partially configured
)

TXQ_CMD = 0
TXQ_CMDLEN = 1
TXQ_CMDACK = 2
TXQ_PORT = 3
TXQ_ARGS = 4
TXQ_RETRIES = 5

LOG_NONE = 0
LOG_ERR = 1
LOG_WARN = 2
LOG_INFO = 3
LOG_DEBUG = 4
LOG_DUMP = 5
LOG_DUMPALL = 6

LOG_NAMES = ["NONE: ", "ERROR:", "WARN: ", "INFO: ", "DEBUG:", "DUMP: "]
