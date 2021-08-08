## Creasol DomBus integration for Home Assistant

Home assistant Custom Component for dealing with [Creasol DomBus RS485 modules](https://www.creasol.it/domotics).

Hundreds of inputs/outputs/sensors can be managed by this integration.

### Features

- Installation through Config Flow UI.
- Manages more than 1 bus, if needed.
- Auto discovery for modules attached to the bus.
- Automatically restore entity configuration when booting HA, to get all entities immediately available.

### Configuration
After custom component installation, reboot HA and 
go to the Configuration -> integrations -> + and select Creasol DomBus protocol

<img src="https://github.com/CreasolTech/home-assistant-creasol-dombus/demo.png?raw=true" alt="Demo">

