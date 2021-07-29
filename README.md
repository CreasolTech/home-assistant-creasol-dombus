[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-creasol-dombus
Home Assistant custom component to manage Creasol DomBus modules to realize a complete domotic network connected by RS485 bus at 115200bps.

# Installation
Copy contents of custom_components folder to your home-assistant config folder or install through HACS.
After reboot of Home-Assistant, this integration can be added through the Configuration -> Integrations -> + ADD INTEGRATION 

```console
cd /tmp
git clone https://github.com/CreasolTech/home-assistant-creasol-dombus.git
cp -a home-assistant-creasol-dombus/custom_components HADIR/config/
```

# Creasol DomBus modules
Domotic modules, optimized for very low power consumption and high reliability, that can be connected together by wired bus, using a common alarm shielded cable within 4 wires: 
* 2x0.22mm² wires for data
* 2x0.5mm² wires for 12-14Vdc power supply 

Using a 13.6V power supply with a lead acid backup battery permits to get domotic system working even in case of power outage: this is perfect expecially for alarm systems.

Actually the following modules are supported:
* [DomBus1](https://www.creasol.it/CreasolDomBus1): 2-3 N.O. relay outputs, 6 digital inputs, 1 230Vac opto-input 
* [DomBus12](https://www.creasol.it/CreasolDomBus12): 7 GPIO, 2 open-drain outputs
* [DomBus23](https://www.creasol.it/CreasolDomBus23): 2 N.O. relay outputs, 1 mosfet output (for 12-24V LED dimming or other DC loads), 2 analog outputs 0-10V, 2 GPIO, 2 low voltage opto-inputs (5-40V), 1 230Vac opto input
* [DomBus31](https://www.creasol.it/CreasolDomBus31): 6 N.O. relay outputs + 2 N.O./N.C. relay outputs
* [DomBusTH](https://www.creasol.it/CreasolDomBusTH): Temperature + Relative Humidity sensors, red + green + white LEDs, 4 GPIO, 2 open-drain outputs, 1 analog input

Modules and components are developed by Creasol, https://www.creasol.it/domotics

## Example of a domotic system managing lights, door bell, alarm, heat pump, ventilation, irrigation, ...

![alt Domotic system using DomBus modules](https://images.creasol.it/AN_domoticz_example2.png)

## Pictures of DomBus modules

![alt DomBus23 image](https://images.creasol.it/creDomBus23_400.png)
![alt DomBus31 image](https://images.creasol.it/creDomBus31_400.png)

![alt DomBusTH image](https://images.creasol.it/creDomBusTH1_200.jpg)
![alt DomBusTH image](https://images.creasol.it/creDomBusTH2_200.jpg)
![alt DomBus12 image](https://images.creasol.it/creDomBus12_400.png)
