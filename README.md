[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-creasol-dombus
Home Assistant custom component to manage Creasol DomBus modules to realize a complete domotic network connected by RS485 bus 115200bps.

# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI

# Creasol DomBus modules
Modules that can be connected together by wire bus, using a common alarm cable with 4 wires: 2 wires for 12V power supply, 2 wires for serial data.
Actually the following modules are supported:
* DomBus1: 2-3 N.O. relay outputs, 6 digital inputs, 1 230Vac opto-input 
* DomBus12: 7 GPIO, 2 open-drain outputs
* DomBus23: 2 N.O. relay outputs, 1 mosfet output (for 12-24V LED dimming or other DC loads), 2 analog outputs 0-10V, 2 GPIO, 2 low voltage opto-inputs (5-40V), 1 230Vac opto input
* DomBus31: 6 N.O. relay outputs + 2 N.O./N.C. relay outputs
* DomBusTH: Temperature + Relative Humidity sensors, red + green + white LEDs, 4 GPIO, 2 open-drain outputs, 1 analog input

<img src="https://images.creasol.it/AN_domoticz_example2.png />

Modules and components are developed by Creasol, https://www.creasol.it
