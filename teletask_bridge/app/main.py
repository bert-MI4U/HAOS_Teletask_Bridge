import asyncio
import signal
import home_assistant as HA
import teletask
import teletask_const as const
import config as Config
import roller_shutters as RS
import platform
import sys
import json

STOP = asyncio.Event()
assets_dict = {}                            # provides a mapping between teletask-ids and loaded assets. allows us to see if we are really monitoring an event or not (teletask just sends everything)
rgbw_groups = {}
rgbw_channels = {}
climate_states = {}

def ask_exit(*args):
    print("stop called, closing down")
    STOP.set()

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def ha_to_teletask_channel(color_value, brightness):
    """Convert HA 0..255 color + brightness to Teletask 0..100."""
    color_value = clamp(int(color_value), 0, 255)
    brightness = clamp(int(brightness), 0, 255)

    level = (color_value / 255) * (brightness / 255) * 100

    return round(level)

async def handle_teletask_event(unit, type, nr, values):
    """Called when a Teletask message arrives.

    Args:
        unit (nr): the number of the unit
        type (string): the Teletask function/type
        nr (number): the asset number
        values (array): the values that were reported
    """
    key = teletask.build_key(unit, type, nr)

    # Handle the normal physical Teletask asset.
    if key in assets_dict:
        asset = assets_dict[key]
        cover_value = None

        HA.send(asset, values)

        # A temperature sensor can additionally expose a climate entity.
        if asset.get('climate', False) and type == 'sensor':
            climate_states[key] = values
            
        if asset['component'] == 'cover':
            cover_value = await RS.handle_cover_event(
                key,
                asset,
                values
            )

        if cover_value:
            HA.send_cover_pos(asset, cover_value)

    # Also update virtual RGBW lights that use this physical dimmer.
    if key in rgbw_channels:
        for rgbw_key, channel in rgbw_channels[key]:
            group = rgbw_groups[rgbw_key]

            # Teletask dimmer feedback is 0..100.
            group[channel] = values[0]

            HA.send_rgbw_state(
                group['asset'],
                group['red'],
                group['green'],
                group['blue'],
                group['white']
            )

async def handle_climate_command(unit, nr, value):
    """Translate Home Assistant MQTT Climate commands to Teletask."""

    sensor_key = teletask.build_key(
        unit,
        'sensor',
        nr
    )

    if sensor_key not in assets_dict:
        print(
            "Climate sensor not found: {}".format(
                sensor_key
            )
        )
        return

    asset = assets_dict[sensor_key]

    if not asset.get('climate', False):
        return

    if '|' not in value:
        return

    command, payload = value.split('|', 1)

    print(
        "climate command {} = {} for {}".format(
            command,
            payload,
            asset['name']
        )
    )

    # -------------------------------------------------------
    # Target temperature
    # -------------------------------------------------------

    if command == 'target_temperature/set':

        if sensor_key not in climate_states:
            print(
                "No current climate state available for {}".format(
                    asset['name']
                )
            )
            return

        state = climate_states[sensor_key]

        current_target = round(
            state['target'] / 10 - 273,
            1
        )

        requested_target = round(
            float(payload) * 2
        ) / 2

        difference = requested_target - current_target

        # Native Teletask adjustment is exactly 0.5 °C.
        steps = round(abs(difference) / 0.5)

        if difference > 0:
            setting = const.SET_TEMPUP
        elif difference < 0:
            setting = const.SET_TEMPDOWN
        else:
            return

        for _ in range(steps):
            await teletask.set_sensor_command(
                asset,
                setting
            )

    # -------------------------------------------------------
    # Preset
    # -------------------------------------------------------

    elif command == 'preset/set':

        preset_map = {
            'day': const.SET_TEMPDAY,
            'night': const.SET_TEMPNIGHT,
            'eco': const.SET_TEMPSTANDBY
        }

        setting = preset_map.get(
            payload.lower()
        )

        if setting is not None:
            await teletask.set_sensor_command(
                asset,
                setting
            )

    # -------------------------------------------------------
    # Fan mode
    # -------------------------------------------------------

    elif command == 'fan_mode/set':

        fan_map = {
            'auto': const.SET_TEMPSPAUTO,
            'low': const.SET_TEMPSPLOW,
            'medium': const.SET_TEMPSPMED,
            'high': const.SET_TEMPSPHIGH
        }

        setting = fan_map.get(
            payload.lower()
        )

        if setting is not None:
            await teletask.set_sensor_command(
                asset,
                setting
            )

    # -------------------------------------------------------
    # HVAC mode
    # -------------------------------------------------------

    elif command == 'mode/set':

        mode_map = {
            'heat': const.SET_TEMPHEAT
        }

        setting = mode_map.get(
            payload.lower()
        )

        if setting is not None:
            await teletask.set_sensor_command(
                asset,
                setting
            )

def load_rgbw_groups(items):
    global rgbw_groups, rgbw_channels

    rgbw_groups = {}
    rgbw_channels = {}

    for asset in items:
        if asset.get('teletask_type') != 'rgbw':
            continue

        key = teletask.build_key_from_asset(asset)

        group = {
            "asset": asset,
            "red": 0,
            "green": 0,
            "blue": 0,
            "white": 0
        }

        rgbw_groups[key] = group

        unit = asset['central_unit']

        channel_map = {
            "red": asset['red'],
            "green": asset['green'],
            "blue": asset['blue'],
            "white": asset['white']
        }

        for channel, dimmer_id in channel_map.items():
            dimmer_key = teletask.build_key(
                unit,
                'dimmer',
                dimmer_id
            )

            rgbw_channels.setdefault(dimmer_key, []).append(
                (key, channel)
            )

    print("loaded {} RGBW group(s)".format(len(rgbw_groups)))


async def calibrate_covers():
    """looks up the list of assets that are used as covers and records the timing for each.
    """
    covers = [value for key, value in assets_dict.items() if value['component'] == 'cover']
    await RS.calibrate(covers)
    for cover in covers:                        # need to let home-assistant know that all covers are closed now
        HA.send_cover_pos(cover, 0)
    
async def handle_rgbw_command(asset, payload):
    key = teletask.build_key_from_asset(asset)
    group = rgbw_groups[key]

    try:
        command = json.loads(payload)
    except Exception as e:
        print("invalid RGBW command: {} ({})".format(payload, e))
        return

    state = command.get('state')

    # Explicit OFF command.
    if state == 'OFF':
        target = {
            "red": 0,
            "green": 0,
            "blue": 0,
            "white": 0
        }

    else:
        color = command.get('color')

        if color:
            brightness = command.get('brightness', 255)

            target = {
                "red": ha_to_teletask_channel(
                    color.get('r', 0),
                    brightness
                ),
                "green": ha_to_teletask_channel(
                    color.get('g', 0),
                    brightness
                ),
                "blue": ha_to_teletask_channel(
                    color.get('b', 0),
                    brightness
                ),
                "white": ha_to_teletask_channel(
                    color.get('w', 0),
                    brightness
                )
            }

        elif 'brightness' in command:
            # Change brightness but preserve the current RGBW proportions.
            brightness = clamp(
                int(command['brightness']),
                0,
                255
            )

            current_max = max(
                group['red'],
                group['green'],
                group['blue'],
                group['white']
            )

            if current_max > 0:
                desired_max = brightness * 100 / 255
                factor = desired_max / current_max

                target = {
                    "red": round(group['red'] * factor),
                    "green": round(group['green'] * factor),
                    "blue": round(group['blue'] * factor),
                    "white": round(group['white'] * factor)
                }
            else:
                # No previous color is known.
                # Use white when only brightness is supplied.
                target = {
                    "red": 0,
                    "green": 0,
                    "blue": 0,
                    "white": round(brightness * 100 / 255)
                }

        elif state == 'ON':
            # ON without a color or brightness.
            # Restore existing values when possible.
            if max(
                group['red'],
                group['green'],
                group['blue'],
                group['white']
            ) > 0:
                target = {
                    "red": group['red'],
                    "green": group['green'],
                    "blue": group['blue'],
                    "white": group['white']
                }
            else:
                target = {
                    "red": 0,
                    "green": 0,
                    "blue": 0,
                    "white": 100
                }

        else:
            return

    # Ensure values remain in Teletask's 0..100 range.
    for channel in target:
        target[channel] = clamp(
            target[channel],
            0,
            100
        )

    channel_ids = {
        "red": asset['red'],
        "green": asset['green'],
        "blue": asset['blue'],
        "white": asset['white']
    }

    for channel in ['red', 'green', 'blue', 'white']:
        dimmer_asset = {
            "name": "{} {}".format(asset['name'], channel),
            "component": "light",
            "teletask_type": "dimmer",
            "central_unit": asset['central_unit'],
            "teletask_id": channel_ids[channel]
        }

        await teletask.set_actuator(
            dimmer_asset,
            str(target[channel])
        )

        group[channel] = target[channel]

    HA.send_rgbw_state(
        asset,
        group['red'],
        group['green'],
        group['blue'],
        group['white']
    )
    
async def calibrate_cover(id):
    id = int(id)
    covers = [value for key, value in assets_dict.items() if value['component'] == 'cover' and value['teletask_id'] == id]
    if len(covers) == 1:
        await RS.calibrate(covers, False)
        HA.send_cover_pos(covers[0], 0)

async def handle_actuator(unit, type, nr, value):
    try:
        if type == 'climate':
            await handle_climate_command(unit,nr,value)
            return
        key = teletask.build_key(unit, type, nr)
        if key in assets_dict:
            asset = assets_dict[key]
            value = value
            if asset['teletask_type'] == 'rgbw':
                await handle_rgbw_command(asset, value)
            elif asset['component'] == 'cover' and value.isnumeric():
                await RS.move_to(key, asset, int(value))
                HA.send_cover_pos(asset, value)
            else:
                await teletask.set_actuator(asset, value)
        elif key == '1_calibrate_-1':
            await calibrate_covers()
        elif key.startswith('1_calibrate_'):
            await calibrate_cover(key[12:])
    except Exception as e:
        print('{}'.format(e))


async def load_assets(items):
    """prepares everything for the assets

    Args:
        items (array): list of assets to create a bridge for
    """
    print("start loading assets")
    
    load_rgbw_groups(items)
    
    for asset in items:                                                     # build the dict so we can use it as a filter on the data coming from teletask
        key = teletask.build_key_from_asset(asset)
        assets_dict[key] = asset
    await HA.load_assets(items)
    await teletask.load_assets(items)
    for key, value in RS.COVER_DATA.items():
        HA.send_cover_pos(assets_dict[key], value['position'])

async def main(loop):
    """
    main loop
    """
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = Config.load(config_path)
    if not config:                                          # something went wrong loading the config, don't continue, exit the app
        return
    RS.load_config()
    started = await HA.start(config['home_assistant'], handle_actuator, loop)
    if not started:
        print('HA not started, stopping')
        return
    started = await teletask.start(config['teletask'], STOP, handle_teletask_event)
    if not started:
        print('teletask not started, stopping')
        return
    asyncio.create_task(load_assets(config['assets']))      # do soon, give teletask read a chance to start
    await teletask.read()                                   # blocks until stop has been set
    await HA.stop()
    RS.save_config()                                        # make certain that the latest cover positions is saved.
    # teletask is already stopped through th stop signal


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    if platform.system() == 'Windows':
        signal.signal(signal.SIGINT, ask_exit)
        signal.signal(signal.SIGTERM, ask_exit)
    else:
        loop.add_signal_handler(signal.SIGINT, ask_exit)
        loop.add_signal_handler(signal.SIGTERM, ask_exit)
    loop.run_until_complete(main(loop))
    loop.close()

