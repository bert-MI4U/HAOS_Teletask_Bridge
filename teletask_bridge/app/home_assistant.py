import asyncio
import json

import teletask

from gmqtt import Client as MQTTClient
from gmqtt import constants as MQTTConst

client = None
discovery_prefix = 'homeassistant'
node_id = "teletask_1"                                  # the id of the teletask device for mqtt topics
on_actuator = None                                      # callback that handles actuator messages for teletask
main_loop = None                                        # async loop
is_connected = False
wait_for_connected = None


def on_connect(client, flags, rc, properties):
    global is_connected
    print('Connected')
    is_connected = True
    if wait_for_connected:                              # could be that other part is still waiting for the connection to be established before continuing
        wait_for_connected.set()

def on_message(client, topic, payload, qos, properties):
    print('RECV MSG:', payload)

    if not on_actuator:
        return

    payload = payload.decode()
    topic_parts = topic.split('/')

    # Climate command:
    #
    # homeassistant/climate/teletask_1/
    # 1_sensor_90_climate/target_temperature/set
    #
    if len(topic_parts) >= 6 and topic_parts[1] == 'climate':
        climate_key = topic_parts[3]

        if climate_key.endswith('_climate'):
            climate_key = climate_key[:-8]

        climate_parts = climate_key.split('_')

        if len(climate_parts) >= 3:
            command = '/'.join(topic_parts[4:])

            main_loop.create_task(
                on_actuator(
                    climate_parts[0],
                    'climate',
                    climate_parts[2],
                    '{}|{}'.format(command, payload)
                )
            )

        return

    # Existing normal Teletask command handling.
    teletask_parts = topic_parts[3].split('_')

    if len(teletask_parts) < 3:
        print("Invalid teletask part: " + topic_parts[3])
    else:
        main_loop.create_task(
            on_actuator(
                teletask_parts[0],
                teletask_parts[1],
                teletask_parts[2],
                payload
            )
        )


def on_disconnect(client, packet, exc=None):
    print('Disconnected')
    global is_connected
    is_connected = False


def on_subscribe(client, mid, qos, properties):
    subscriptions = client.get_subscriptions_by_mid(mid)
    for subscription, granted_qos in zip(subscriptions, qos):
        if granted_qos == 0:
            print('subscribed to topic: {}'.format(subscription.topic))
        else:
            print('failed to subscribe to topic: {}'.format(subscription.topic))

async def start(config, callback, loop):
    global client, discovery_prefix, on_actuator, node_id, main_loop
    print("starting home-assistant connection")
    on_actuator = callback
    main_loop = loop
    discovery_prefix = config['discovery_prefix']
    node_id = config['device_id']

    client = MQTTClient(config['client_id'])

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe

    try:
        await client.connect(config['broker_host'])
        return True
    except Exception as e:
        print('{}'.format(e))
        return False


async def stop():
    """
    close the connection
    """
    global client
    if client:
        await client.disconnect()
        client = None


def build_asset_def(base_topic, asset, key, is_first):
    payload = {
        "~": base_topic,
        "name": asset['name'],
        "unique_id": key,
        "stat_t": "~/state",
        "dev": {
            "ids": ["teletask"]
        }
    }
    # Virtual RGBW light composed of four Teletask dimmers, Use Home Assistant's MQTT JSON light schema.
    if asset['teletask_type'] == 'rgbw':
        payload['schema'] = 'json'
        payload['cmd_t'] = '~/set'
        payload['sup_clrm'] = ['rgbw']
        
    if is_first:
        payload['dev']['mf'] = "teletask"
        payload['dev']['mdl'] = "micros+"

    if asset['component'] == 'button':
        payload['command_topic'] = "~/exec"
    else:
        if asset['component'] not in ['sensor', 'binary_sensor']:
            payload['cmd_t'] = "~/set"
        if 'device_class' in asset:
            payload['device_class'] = asset['device_class']
        if 'unit_of_measurement' in asset:
            payload['unit_of_measurement'] = asset['unit_of_measurement']
        if 'state_class' in asset:
            payload['state_class'] = asset['state_class']
        if asset['teletask_type'] == 'dimmer':
            payload['bri_cmd_t'] = '~/setbri'
            payload['bri_stat_t'] = '~/statebri'
            payload['bri_scl']=100
            payload['on_command_type'] = 'brightness' # only send brigthness instruction don't include on/off
        if asset['component'] == 'cover':
            payload['position_topic'] = '~/pos'
            payload['set_position_topic'] = '~/setpos'
        if asset['component'] == 'binary_sensor':
            payload['pl_on'] = 'ON'
            payload['pl_off'] = 'OFF'
    return payload

def load_asset(asset, is_first):
    key = teletask.build_key_from_asset(asset)
    base_topic = '{}/{}/{}/{}'.format(discovery_prefix, asset['component'], node_id, key)
    config_topic = '{}/config'.format(base_topic)
    payload = build_asset_def(base_topic, asset, key, is_first)
    client.publish(config_topic, bytearray(json.dumps(payload), 'utf-8'), qos=1)

async def load_assets(items):
    """
    let home assistant know which sensors & actuators we have
    - wait until connected
    - send discovery topics
    - subscribe to actuator commands
    """ 
    global wait_for_connected
    if not client:
        raise Exception("home-assistant not connected")
    if not is_connected:
        wait_for_connected = asyncio.Event()                    # let the event handler know we want to get warned
        await wait_for_connected.wait()
        wait_for_connected = None
    print("sending discovery data to home assistant")
    has_covers = False
    is_first = True
    for asset in items:
        load_asset(asset, is_first)
        if asset.get('climate', False):
            load_climate_asset(asset)
        is_first = False
        is_cover = asset['component'] == 'cover'
        if is_cover:
            asset = {"name": "calibrate cover {}".format(asset['name']), "component": "button", "teletask_type": "calibrate", "central_unit": 1, "teletask_id": asset['teletask_id']}    
            load_asset(asset, is_first)
        has_covers = has_covers or is_cover
    if has_covers:
        asset = {"name": "calibrate covers", "component": "button", "teletask_type": "calibrate", "central_unit": 1, "teletask_id": -1}
        load_asset(asset, is_first)
        client.subscribe('{}/+/{}/+/exec'.format(discovery_prefix, node_id))
    # need to get messages sent to this device for all actuators
    client.subscribe('{}/+/{}/+/set'.format(discovery_prefix, node_id))
    client.subscribe('{}/+/{}/+/setbri'.format(discovery_prefix, node_id))
    if has_covers:
        client.subscribe('{}/+/{}/+/setpos'.format(discovery_prefix, node_id))
    client.subscribe('{}/climate/{}/+/target_temperature/set'.format(discovery_prefix,node_id))
    client.subscribe('{}/climate/{}/+/preset/set'.format(discovery_prefix,node_id))
    client.subscribe('{}/climate/{}/+/fan_mode/set'.format(discovery_prefix,node_id))
    client.subscribe('{}/climate/{}/+/mode/set'.format(discovery_prefix,node_id))

def get_value(asset, value, as_dimmer=False):
    """convert the value to something home assistant can work with
    """
    component = asset['component']
    result = None
    
    if component == 'light':
        if as_dimmer:
            result = '{}'.format(value[0])        # when as dimmer, always use the actual value
        else:
            if value[0] == 0:                     # need to compare the value, not the array
                result = 'OFF'
            else:
                result = 'ON'

    elif component == 'switch' and asset['teletask_type'] in ['relay', 'genmood', 'locmood']:
        if value[0] == 0:
            result = 'OFF'
        else:
            result = 'ON'
 
    elif component == 'binary_sensor':
        if value[0] == 0:
            result = 'OFF'
        else:
            result = 'ON'
            
    elif component == 'cover':
        # print("values: {}".format(value))
        if value[1] == 0:
            result = 'stopped'
        elif value[0] == 2:
            result = 'closing'
        else:
            result = 'opening'

    elif component == 'sensor':
        device_class = asset.get('device_class')
    
        # Teletask sensor reports are now decoded as dictionaries.
        if isinstance(value, dict):
            raw_value = value['value']
        else:
            raw_value = value
    
        if device_class == 'temperature':
            # Teletask temperature: Kelvin x 10
            result = '{}'.format(
                round(raw_value / 10 - 273, 2)
            )
        elif device_class == 'power':
            # Teletask power sensor: raw value x 10 = Watts
            result = '{}'.format(
                raw_value * 10
            )
        elif device_class == 'wind_speed':
            # Teletask wind speed is transmitted as knots x 10
            result = '{}'.format(
                round(raw_value / 10, 1)
            )
        elif device_class == 'precipitation':
            # Teletask precipitation: assumed raw value x 100
            # Verify scaling during actual rainfall
           result = '{}'.format(
                round(raw_value / 100, 2)
            )
        elif device_class == 'illuminance':
            # Teletask illuminance: lux x 10
            result = '{}'.format(
                round(raw_value / 10, 1)
            )   
        else:
            result = '{}'.format(raw_value)
        
    if result == None:
        result = value                              # return the full array cause mqtt publish wants a byte array
    else:
        result = bytearray(result, 'utf-8')
    return result

def sensor_value_to_temperature(raw):
    return round(raw / 10 - 273, 1)



def load_climate_asset(asset):
    """Register an additional MQTT climate entity for a Teletask sensor."""

    sensor_key = teletask.build_key_from_asset(asset)
    climate_key = '{}_climate'.format(sensor_key)

    base_topic = '{}/climate/{}/{}'.format(
        discovery_prefix,
        node_id,
        climate_key
    )

    config_topic = '{}/config'.format(base_topic)

    payload = {
        "~": base_topic,
        "name": asset['name'],
        "unique_id": climate_key,

        "curr_temp_t": "~/current_temperature",

        "temp_stat_t": "~/target_temperature",
        "temp_cmd_t": "~/target_temperature/set",

        "mode_stat_t": "~/mode",
        "mode_cmd_t": "~/mode/set",
        "modes": ["heat", "cool"],

        "pr_mode_stat_t": "~/preset",
        "pr_mode_cmd_t": "~/preset/set",
        "pr_modes": ["day", "night", "eco"],

        "fan_mode_stat_t": "~/fan_mode",
        "fan_mode_cmd_t": "~/fan_mode/set",
        "fan_modes": ["auto", "low", "medium", "high"],

        "act_t": "~/action",

        "temp_unit": "C",
        "temp_step": 0.5,

        "min_temp": asset.get("min_temp", 10),
        "max_temp": asset.get("max_temp", 30),

        "dev": {
            "ids": ["teletask"]
        }
    }

    client.publish(
        config_topic,
        bytearray(json.dumps(payload), 'utf-8'),
        qos=1
    )

def send(asset, value):
    if not client:
        raise Exception("not connected")
    key = teletask.build_key_from_asset(asset)
    if asset['teletask_type'] == 'dimmer':
        to_send = get_value(asset, value, False)
        topic = '{}/{}/{}/{}/state'.format(discovery_prefix, asset['component'], node_id, key)
        print("publishing to: {}, value: {}".format(topic, to_send))
        client.publish(topic, to_send, qos=0)

        to_send = get_value(asset, value, True)
        topic = '{}/{}/{}/{}/statebri'.format(discovery_prefix, asset['component'], node_id, key)
        print("publishing to: {}, value: {}".format(topic, to_send))
        client.publish(topic, to_send, qos=0)
    else:
        to_send = get_value(asset, value)
        topic = '{}/{}/{}/{}/state'.format(discovery_prefix, asset['component'], node_id, key)
        print("publishing to: {}, value: {}".format(topic, to_send))
        client.publish(topic, to_send, qos=0)

    # A Teletask temperature sensor can additionally expose
    # a Home Assistant climate entity.
    if asset.get('climate', False):
        print(
            "CLIMATE DEBUG {} received: {}".format(
                asset['name'],
                value
            )
        )
        send_climate_state(asset, value)

def send_rgbw_state(asset, red, green, blue, white):
    """Publish the combined state of four Teletask dimmers as one RGBW light.
    Teletask channel values are 0..100. Home Assistant RGBW color values are 0..255.
    """
    if not client:
        raise Exception("not connected")

    key = teletask.build_key_from_asset(asset)
    channels = [red, green, blue, white]
    maximum = max(channels)

    if maximum <= 0:
        brightness = 0
        rgbw = [0, 0, 0, 0]
        state = 'OFF'
    else:
        # Overall brightness comes from the strongest channel.
        brightness = round(maximum * 255 / 100)

        # Normalize the color independently of brightness.
        rgbw = [
            round(red * 255 / maximum),
            round(green * 255 / maximum),
            round(blue * 255 / maximum),
            round(white * 255 / maximum)
        ]
        state = 'ON'
    payload = {
        "state": state,
        "brightness": brightness,
        "color_mode": "rgbw",
        "color": {
            "r": rgbw[0],
            "g": rgbw[1],
            "b": rgbw[2],
            "w": rgbw[3]
        }
    }
    topic = '{}/{}/{}/{}/state'.format(
        discovery_prefix,
        asset['component'],
        node_id,
        key
    )

    print(
        "publishing RGBW to: {}, value: {}".format(
            topic,
            payload
        )
    )

    client.publish(
        topic,
        bytearray(json.dumps(payload), 'utf-8'),
        qos=0
    )
    
def send_cover_pos(asset, value):
    """special function to send the current position of the cover to this specific topic.

    Args:
        asset (object): the asset to send the value for
        value (integer): position of the cover
    """
    if not client:
        raise Exception("not connected")
    key = teletask.build_key_from_asset(asset)
    topic = '{}/{}/{}/{}/pos'.format(discovery_prefix, asset['component'], node_id, key)
    print("publishing to: {}, value: {}".format(topic, value))
    client.publish(topic, value, qos=0)

def send_climate_state(asset, value):
    """Publish complete Teletask climate state to Home Assistant."""

    if not client:
        raise Exception("not connected")

    if not isinstance(value, dict):
        print(
            "climate {}: expected dict, got {}".format(
                asset['name'],
                value
            )
        )
        return

    required = [
        'value',
        'target',
        'preset',
        'mode',
        'speed_mode',
        'power'
    ]

    missing = [
        field
        for field in required
        if field not in value
    ]

    if missing:
        print(
            "climate {}: missing fields {}, received {}".format(
                asset['name'],
                missing,
                value
            )
        )
        return

    sensor_key = teletask.build_key_from_asset(asset)
    climate_key = '{}_climate'.format(sensor_key)

    base_topic = '{}/climate/{}/{}'.format(
        discovery_prefix,
        node_id,
        climate_key
    )

    current_temp = sensor_value_to_temperature(
        value['value']
    )

    target_temp = sensor_value_to_temperature(
        value['target']
    )

    # -------------------------------------------------------
    # Preset
    # -------------------------------------------------------

    preset_code = value['preset']

    target_raw = value['target']
    day_raw = value.get('day')
    night_raw = value.get('night')

    if preset_code == 26 and target_raw == day_raw:
        preset = 'day'

    elif preset_code == 25 and target_raw == night_raw:
        preset = 'night'

    elif preset_code == 93:
        preset = 'eco'

    else:
        preset = 'none'

    # -------------------------------------------------------
    # HVAC mode
    # -------------------------------------------------------

    mode_map = {
        94: 'heat',
        95: 'heat',
        96: 'cool',
        106: 'off'
    }

    mode = mode_map.get(
        value['mode'],
        'heat'
    )

    # -------------------------------------------------------
    # Fan mode
    # -------------------------------------------------------

    fan_map = {
        89: 'auto',
        97: 'low',
        98: 'medium',
        99: 'high'
    }

    fan_mode = fan_map.get(
        value['speed_mode'],
        'auto'
    )

    # -------------------------------------------------------
    # HVAC action
    # -------------------------------------------------------

    # The Teletask Power field is not a reliable heating-demand
    # indication for this installation.
    if current_temp < target_temp:
        action = 'heating'
    else:
        action = 'idle'

    states = {
        'current_temperature': current_temp,
        'target_temperature': target_temp,
        'mode': mode,
        'preset': preset,
        'fan_mode': fan_mode,
        'action': action
    }

    print(
        "climate {} decoded: {}".format(
            asset['name'],
            states
        )
    )

    for subtopic, state in states.items():

        topic = '{}/{}'.format(
            base_topic,
            subtopic
        )

        print(
            "publishing climate to: {}, value: {}".format(
                topic,
                state
            )
        )

        client.publish(
            topic,
            str(state),
            qos=0
        )
