import os
import sys
import logging as log
import time
import atexit
import asyncio
import binascii
from datetime import datetime
import subprocess
import evdev
import yaml
from evdev import InputDevice, categorize, ecodes
import RPi.GPIO as GPIO
from beacontools import BeaconScanner, IBeaconFilter

def name_to_hex(name):
    name = name + "                "
    name = name[:16]
    hex_name = str(binascii.hexlify(bytes(name, 'utf-8')))[2:-1]
    index = 0
    formatted_hex_name = ""
    for character in hex_name:
        formatted_hex_name = formatted_hex_name + character
        if index % 2 == 1:
            formatted_hex_name = formatted_hex_name + " "
        index += 1
    return formatted_hex_name[:-1]

def number_to_hex(number):
    number = str(hex(number))[2:]
    number = "0000" + number
    number = number[-4:-2] + " " + number[-2:]
    return number

with open('/badge/config.yaml', "r") as f:
    config = yaml.load(f)

try:
    with open(os.path.join(sys.path[0], 'hacks.yaml'), "r") as f:
        hacks = yaml.load(f)
except FileNotFoundError:
    hacks = {}

if config['debug']:
    log.basicConfig(format="[%(asctime)s] [%(levelname)s] %(message)s", level=log.DEBUG, filename='/badge/logs/mcp.log')
else:
    log.basicConfig(format="[%(asctime)s] [%(levelname)s] %(message)s", level=log.INFO, filename='/badge/logs/mcp.log')

log.info("Script started")
log.debug(config)

# Global state dict
state = {
    'waifus': True,         # Main screen
    'slideshow': False,     # Slideshow screen/mode
    'init_hack': False,     # Initiating hack screen/video
    'hacked': False,        # Badge hacked screen (lock out other functions/screens)
    'vibe': False,          # Vibration control screen
    'vibe_active': False    # Vibration active screen
}

slideshow_controls = {
    'next': False,
    'previous': False
}

# Global tap counts
tap_counts = {
    'last': None,   # Timestamp
    'vibe': 0,          # Counter to activate vibration control screen
    'hacked': 0         # Counter to disable hacked state
}

name = None
major = None

# Kill all omxplayer instances on exit
atexit.register(subprocess.call, ['killall', '/usr/bin/omxplayer.bin'])

# Make sure vibration motor is off
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(18,GPIO.OUT)
log.debug('Motor turned off')

# Run subprocess using standard set of parameters
def proc_open(command):
    log.debug('Running command: {0}'.format(command))
    command = command.split(' ')
    return subprocess.Popen(command, stdin=subprocess.PIPE, shell=False, preexec_fn=os.setsid)

async def waifus_handler():
    global state
    while True:
        if not state['waifus']:
            await asyncio.sleep(.1)
        else:
            log.info('Starting waifus background animation')
            path = os.path.join('/badge/default.mp4')
            process = proc_open('omxplayer --loop --no-osd --layer 1 {0}'.format(path))
            while process.poll() == None:
                if not state['waifus']:
                    process.communicate(b'q')
                    log.info('Terminated waifus background animation')
                    break
                await asyncio.sleep(.1)

def validate_beacon(bt_addr, rssi, packet, additional_info):
    global state
    global name
    global major
    minor = additional_info['minor']
    major = additional_info['major']
    if minor == 1337:
        uuid = additional_info['uuid'].replace('-', '')
        name = bytes.fromhex(uuid).decode()
        if name.replace(' ', '') == config['username'].replace(' ', ''):
            print("Ignoring own hack: {} {}".format(name, major))
            return
        if name not in hacks:
            hacks[name] = major
            with open(os.path.join(sys.path[0], 'hacks.yaml'), 'w') as f:
                yaml.dump(hacks, f, default_flow_style=False)
            print("Detected new hack: {} {}".format(name, major))
            state['hacked'] = True
        else:
            if additional_info['major'] > hacks[name]:
                hacks[name] = major
                with open(os.path.join(sys.path[0], 'hacks.yaml'), 'w') as f:
                    yaml.dump(hacks, f, default_flow_style=False)
                print("Detected new hack: {} {}".format(name, major))
                state['hacked'] = True
            else:
                print("Ignoring previous hack: {} {}".format(name, major))
        if config['hack']['can_hack'] == False:
            config['hack']['can_hack'] = True
            with open(os.path.join(sys.path[0], 'config.yaml'), 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
    return

async def hack_handler():
    global state
    global tap_counts
    scanner = BeaconScanner(validate_beacon)
    scanner.start()
    log.info('Started beacon scanner')
    while True:
        if not state['hacked']:
            await asyncio.sleep(.1)
        else:
            scanner.stop()
            log.info('Starting hack animation')
            path = os.path.join(sys.path[0], 'media','waifu_hack.mp4')
            process = proc_open('omxplayer --loop --no-osd --layer 5 {0}'.format(path))
            tap_counts['hacked'] = 0
            path = os.path.join(sys.path[0], 'scripts','send_beacon_start.sh')
            hex_name = name_to_hex(name)
            hex_number = number_to_hex(major)
            hack_start_process = subprocess.Popen(['sudo', path, hex_name, hex_number])

            while process.poll() == None:
                GPIO.output(18,GPIO.HIGH)
                await asyncio.sleep(.5)
                GPIO.output(18,GPIO.LOW)

                # If hack terminated, close the video
                if not state['hacked']:
                    process.communicate(b'q')
                    log.info('Terminated hack animation and vibration (#1)')
                    await asyncio.sleep(5)
                    path = os.path.join(sys.path[0], 'scripts','send_beacon_end.sh')
                    hack_end_process = subprocess.Popen(['sudo', path])
                    await asyncio.sleep(5)
                    scanner = BeaconScanner(validate_beacon)
                    scanner.start()
                    log.info('Restarted beacon scanner')
                    break

                await asyncio.sleep(.2)
                GPIO.output(18,GPIO.HIGH)
                await asyncio.sleep(1)
                GPIO.output(18,GPIO.LOW)

                # Second check to improve resposiveness when exiting hack
                if not state['hacked']:
                    process.communicate(b'q')
                    log.info('Terminated hack animation and vibration (#2)')
                    await asyncio.sleep(5)
                    path = os.path.join(sys.path[0], 'scripts','send_beacon_end.sh')
                    hack_end_process = subprocess.Popen(['sudo', path])
                    await asyncio.sleep(5)
                    scanner = BeaconScanner(validate_beacon)
                    scanner.start()
                    log.info('Restarted beacon scanner')
                    break

                await asyncio.sleep(.5)
        if state['init_hack']:
            log.info('Displaying init_hack animation')
            path = os.path.join(sys.path[0], 'media','hacking.mp4')
            hack_video = proc_open('omxplayer --loop --no-osd --layer 2 --blank {0}'.format(path))
            scanner.stop()
            log.info('Sending hack beacon')
            path = os.path.join(sys.path[0], 'scripts','send_beacon.sh')
            hex_name = name_to_hex(config['username'])
            if 'self' in hacks:
                hacks['self'] = hacks['self'] + 1
            else:
                hacks['self'] = 1
            hex_number = number_to_hex(hacks['self'])
            with open(os.path.join(sys.path[0], 'hacks.yaml'), 'w') as f:
                yaml.dump(hacks, f, default_flow_style=False)
            hack_process = subprocess.Popen(['sudo', path, hex_name, hex_number])
            while hack_process.poll() == None:
                await asyncio.sleep(.1)
            scanner = BeaconScanner(validate_beacon)
            scanner.start()
            log.info('Restarted beacon scanner')
            state['init_hack'] = False
            hack_video.communicate(b'q')
            log.info('Terminated init_hack animation')

async def vibe_handler():
    global state
    while True:
        if not state['vibe']:
            await asyncio.sleep(.1)
        else:
            log.info('Starting both vibration animations')
            background_path = os.path.join(sys.path[0], 'media','vibe.mp4')
            background = proc_open('omxplayer --loop --no-osd --layer 3 {0}'.format(background_path))

            foreground_path = os.path.join(sys.path[0], 'media','vibe_active.mp4')
            foreground = proc_open('omxplayer --win 0,0,640,480 --loop --no-osd --layer 4 --alpha 0 --dbus_name org.vibe_active {0}'.format(foreground_path))
            while background.poll() == None:
                if state['vibe_active']:
                    GPIO.output(18,GPIO.HIGH)
                else:
                    if not state['hacked']:
                        GPIO.output(18,GPIO.LOW)
                if not state['vibe']:
                    background.communicate(b'q')
                    foreground.communicate(b'q')
                    log.info('Terminated vibration animations')
                    break
                await asyncio.sleep(.05)

async def slideshow_handler():
    global state
    global slideshow_controls
    while True:
        if not state['slideshow']:
            await asyncio.sleep(.1)
        else:
            files = os.listdir('/badge/slideshow')
            log.debug('Found the following slideshow files:')
            for file in files:
                log.debug(file)

            index = 0
            while True:
                if index > len(files) - 1:
                    index = 0
                elif index < 0:
                    index = len(files) - 1
                if not state['slideshow']:
                    break
                log.debug('Slideshow index: {index} of {total}'.format(index=index, total=len(files)))

                file = files[index]
                path = os.path.join('/badge/slideshow', file)
                log.debug('Playing: {0}'.format(path))

                process = proc_open('omxplayer --layer 2 --no-osd --aspect-mode fill {}'.format(path))

                while process.poll() == None:
                    if not state['slideshow']:
                        process.communicate(b'q')
                        log.info('Terminated slideshow')
                        break
                    if slideshow_controls['next']:
                        log.info('Slideshow next button pressed')
                        process.communicate(b'q')
                        slideshow_controls['next'] = False
                        break
                    if slideshow_controls['previous']:
                        log.info('Slideshow previous button pressed')
                        process.communicate(b'q')
                        slideshow_controls['previous'] = False
                        index -= 2
                        break
                    await asyncio.sleep(.05)
                index += 1

async def event_handler():
    global state
    global slideshow_controls
    global tap_counts

    x = 0
    y = 0

    device = evdev.InputDevice('/dev/input/event0')

    async for event in device.async_read_loop():
        if event.type == ecodes.EV_ABS:
            absevent = categorize(event)
            if ecodes.bytype[absevent.event.type][absevent.event.code] == "ABS_X":
                x = absevent.event.value
            elif ecodes.bytype[absevent.event.type][absevent.event.code] == "ABS_Y":
                y = absevent.event.value

        quad = get_quad(x, y)

        if event.type == ecodes.EV_KEY and event.value == 1:
            log.debug("Touch event down: x={x} y={y} quad={quad}".format(x=x, y=y, quad=quad))
            log.debug("Previous state: {0}".format(state))

            if not state['hacked'] and not state['vibe']:
                await haptic_feedback()
            if state['vibe']:
                log.info('Showing vibration active animation')
                state['vibe_active'] = True
                path = os.path.join(sys.path[0], 'scripts','dbuscontrol.sh')
                proc_open('{0} org.vibe_active setalpha 255'.format(path))

            if state['hacked']:
                tap_counts['hacked'] += 1
                log.debug('Trying to deactivate hack, tap #{0}'.format(tap_counts['hacked']))
                if tap_counts['hacked'] > 5:
                    log.info('Hack deactivated')
                    state['hacked'] = False
        elif event.type == ecodes.EV_KEY and event.value == 0:
            # Wait until we have x and y
            if x == 0 or y == 0:
                continue

            log.debug("Touch event up: x={x} y={y} quad={quad}".format(x=x, y=y, quad=quad))
            log.debug("Previous state: {0}".format(state))

            state['vibe_active'] = False

            if state['vibe']:
                log.info('Hiding vibration active animation')
                path = os.path.join(sys.path[0], 'scripts','dbuscontrol.sh')
                proc_open('{0} org.vibe_active setalpha 0'.format(path))

            if state['slideshow']:
                if quad == 2:
                    state['slideshow'] = False
                elif quad == 3:
                    slideshow_controls['previous'] = True
                elif quad == 4:
                    slideshow_controls['next'] = True
            elif state['vibe']:
                # Prevent exiting vibe prematurely
                if quad == 2 and (datetime.now() - tap_counts['last']).total_seconds() > 1:
                    state['vibe'] = False
            else:
                if quad == 1:
                    state['slideshow'] = True
                elif quad == 2:
                    if tap_counts['last'] != None:
                        if (datetime.now() - tap_counts['last']).total_seconds() < 1:
                            tap_counts['vibe'] += 1
                        else:
                            tap_counts['vibe'] = 1
                    tap_counts['last'] = datetime.now()
                    if tap_counts['vibe'] > 4:
                        state['vibe'] = True
                        tap_counts['vibe'] = 0
                elif quad == 4:
                    state['init_hack'] = True

            log.debug("New state: {0}".format(state))
            # Clear out x and y
            x = 0
            y = 0

def get_quad(x, y):
    if x == 0 or y == 0:
        return False

    if x < 1088:
        if y < 1048:
            return 1
        elif y > 3048:
            return 3
    elif x > 3088:
        if y < 1048:
            return 2
        elif y > 3048:
            return 4
    return False

async def haptic_feedback():
    GPIO.output(18,GPIO.HIGH)
    time.sleep(.1)
    GPIO.output(18,GPIO.LOW)

asyncio.ensure_future(waifus_handler())
asyncio.ensure_future(hack_handler())
asyncio.ensure_future(vibe_handler())
asyncio.ensure_future(slideshow_handler())
asyncio.ensure_future(event_handler())

loop = asyncio.get_event_loop()
loop.run_forever()
