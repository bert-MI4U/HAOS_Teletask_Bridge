# teletask_bridge
A teletask to home-assistant bridge

This application allows you to take full control of your teletask setup through the home-assistant gateway. It registers your teletask unit as an mqtt device and adds all the sensors/actuators that you have defined in the config.

## installation as HAOS add-on

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

goto settings/apps  
click on install app  
click on tree dots at the top and select repositories  
paste the URL "https://github.com/bert-MI4U/teletask_bridge_HAaddon" and press add.

select the Teletask Bridge from the App Store and install

configure the config.json file (see [below](#configuration))  
use Studio Code Server (or other)    
create a Teletask folder in the /config folder
create a config.json file
copy the config.json contents below to this file.


## configuration
Auto discovery is used on the home-automation side to load all the assets. Teletask however doesn't support auto-discovery, so you will have to define the list yourself.
All config data is stored in the file `config.json`, located in the application folder. It requires the following sections:

- home_assistant: broker details
  - discovery_prefix: topic prefix used for auto-discovery. Usually `homeassistant`
  - client_id: identify this client with the broker, should be unique for each device
  - broker_host: name/ip address of the broker
  - device_id: identifier for this device in home-assistant
- teletask: all the details to connect to the teletask device
  - ip: the ip address of the teletask unit
  - port: the port number to connect to.
- assets: all the sensors and actuators that you would like to have registered in home-assistant.
  - name: label used in home-assistant
  - component: the mqtt component used to register the asset in home assistant. See [mqtt configuration](https://www.home-assistant.io/integrations/mqtt/#configure-mqtt-options) for more info.
  - teletask_type: the type of the component on the teletask side. Supported types are:
    - relay
    - dimmer
    - motor
    - locmood
    - timedmood
    - genmood
    - flag
    - sensor
    - process
    - regime
    - service
    - cond
  - teletask_id: the id number to identify the item in teletask. This can be found with the prosoft application of teletask.


 Sample config.json file

``` {
    "home_assistant": {
        "discovery_prefix": "homeassistant",
        "client_id": "teletask_bridge",
        "broker_host": "192.168.1.200",
        "device_id": "teletask_1"
    },
    "teletask": {
        "ip": "192.168.1.1",
        "port": 55957
    },
    "assets": [
        {"name": "Garage", "component": "light", "teletask_type": "relay", "central_unit": 1, "teletask_id": 1},
 
        {"name": "Oprit", "component": "light", "teletask_type": "locmood", "central_unit": 1, "teletask_id": 5},

        {"name": "Sauna R", "component": "light", "teletask_type": "dimmer", "central_unit": 1, "teletask_id": 1},
        {"name": "Sauna G", "component": "light", "teletask_type": "dimmer", "central_unit": 1, "teletask_id": 2},
        {"name": "Sauna B", "component": "light", "teletask_type": "dimmer", "central_unit": 1, "teletask_id": 3},
        {"name": "Sauna W", "component": "light", "teletask_type": "dimmer", "central_unit": 1, "teletask_id": 4},

        {"name": "Werkbank 1", "component": "switch", "teletask_type": "relay", "central_unit": 1, "teletask_id": 7},
        
        {"name": "TV-kijken", "component": "switch", "teletask_type": "genmood", "central_unit": 1, "teletask_id": 6},

        {"name": "Zomer", "component": "switch", "teletask_type": "flag", "central_unit": 1, "teletask_id": 5},

        {"name": "Screens Weather", "component": "switch", "teletask_type": "process", "central_unit": 1, "teletask_id": 26},
        
        {"name": "Regen", "component": "switch", "teletask_type": "cond", "central_unit": 1, "teletask_id": 2},

        {"name": "Living", "component": "sensor", "device_class": "temperature", "unit_of_measurement": "°C", "teletask_type": "sensor", "central_unit": 1, "teletask_id": 90},
    ]
}
```

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

