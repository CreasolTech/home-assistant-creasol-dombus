[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-creasol-dombus
Home Assistant custom component to manage Creasol DomBus modules to realize a complete domotic network connected by RS485 bus at 115200bps.

This software comes with ABSOLUTE NO WARRANTY.

# Installation using HACS
This is the preferred way to install the Creasol DomBus component, because it permits to easily update it.

Using Home Assistant Community Store, open HACS panel -> Integrations -> search from 'Creasol DomBus' and click on INSTALL

# Manual installation (if HACS is not installed)
Copy contents of custom_components folder to your home-assistant config folder or install through HACS.

```console
cd /tmp
git clone https://github.com/CreasolTech/home-assistant-creasol-dombus.git
cp -a home-assistant-creasol-dombus/custom_components HADIR/config/
# command for Hassio:  cp -a home-assistant-creasol-dombus/custom_components /config/
ha core restart
```

After reboot of Home-Assistant, this integration can be added through the Configuration -> Integrations -> + ADD INTEGRATION 
and selecting Creasol DomBus integration.


## DomBus modules for Domoticz and Home Assistant
**DomBus are domotic modules, optimized for very low power consumption and high reliability, with inputs, outputs and sensors** (temperature, relative humidity, distance).

DomBus modules can be connected together by **wired bus**, using a **common alarm shielded cable within 4 wires**:
* 2x0.22mm² wires for data
* 2x0.5mm² wires for 12-14Vdc power supply

Using a 13.6V power supply with a lead acid backup battery permits to get **domotic system working even in case of power outage**: this is perfect even for alarm systems.

Actually the following modules are supported:
* [DomBusTH](https://www.creasol.it/CreasolDomBusTH): **Temperature + Relative Humidity sensors, red + green + white LEDs, 4 GPIO, 2 open-drain outputs, 1 analog input**
* [DomBus12](https://www.creasol.it/CreasolDomBus12): **7 GPIO, 2 open-drain outputs**
* [DomBus23](https://www.creasol.it/CreasolDomBus23): **2 N.O. relay outputs, 1 mosfet output** (for 12-24V LED dimming or other DC loads), **2 analog outputs 0-10V, 2 GPIO, 2 low voltage opto-inputs (5-40V), 1 230Vac opto input**
* [DomBus31](https://www.creasol.it/CreasolDomBus31): very low power consumption module with **6 N.O. relay outputs + 2 N.O./N.C. relay outputs**
* [DomBus32](https://www.creasol.it/CreasolDomBus31): **3 relays + 3 AC inputs** with a single common (line or neutral), and **5 I/Os**
* [DomBus36](https://www.creasol.it/CreasolDomBus31): **3 groups of (4 relays + common)**: 12mW power consumption with all relays OFF, less than 750mW with all relays ON!

Modules and components are developed by Creasol, https://www.creasol.it/domotics

## Pictures of DomBus modules

[![alt DomBus23 image](https://images.creasol.it/creDomBus23_400.png "DomBus23: 2 N.O. relay outputs, 1 mosfet output for 12-24V LED dimming or other DC loads, 2 analog outputs 0-10V, 2 GPIO, 2 low voltage opto-inputs 5-40V, 1 230Vac opto input")](https://www.creasol.it/CreasolDomBus23)
[![alt DomBus31 image](https://images.creasol.it/creDomBus31_400.png "DomBus31: low power module with 6 N.O. relay outputs + 2 N.O./N.C. relay outputs")](https://www.creasol.it/CreasolDomBus31)

[![alt DomBusTH image](https://images.creasol.it/creDomBusTH2_200.jpg "DomBusTH front view with white led, red/green led, temperature + humidity sensor")](https://www.creasol.it/CreasolDomBusTH)
[![alt DomBusTH image](https://images.creasol.it/creDomBusTH6_200.webp "DomBusTH: module with temp+humidity sensors, 3 LEDs, 4 I/O, 2 outputs, 1 analog input")](https://www.creasol.it/CreasolDomBusTH)
[![alt DomBus12 image](https://images.creasol.it/creDomBus12_400.png "DomBus12: 7 I/Os + 2 open-drain outputs that can be connected to 2 external relays")](https://www.creasol.it/CreasolDomBus12)
[![alt DomBus32 image](https://images.creasol.it/creDomBus32_3_200.webp "DomBus32: 3 relays, 3 AC inputs, 5 I/Os")](https://www.creasol.it/DomBus32)
[![alt DomBus36 image](https://images.creasol.it/creDomBus36_400.webp "DomBus36: 12 relays module with very low power consumption")](https://www.creasol.it/DomBus36)


## Example of a domotic system managing lights, door bell, alarm, heat pump, ventilation, irrigation, ...

![alt Domotic system using DomBus modules](https://images.creasol.it/AN_domoticz_example2.png "Example of a domotic system managing lights, door bell, alarm, heat pump, ventilation, irrigation, ...")

