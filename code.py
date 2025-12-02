# SPDX-License-Identifier: MIT
import gc

import board
import neopixel
import json
import wifi
import time
import os
import supervisor
import adafruit_logging
import adafruit_connection_manager
import adafruit_minimqtt.adafruit_minimqtt
from adafruit_minimqtt.adafruit_minimqtt import MMQTTException
from adafruit_minimqtt.adafruit_minimqtt import MMQTTStateError
from adafruit_led_animation.group import AnimationGroup
from adafruit_led_animation.sequence import AnimationSequence
from circuitpy_helpers.led_animations import animationBuilder
from circuitpy_helpers.file_helpers import updateFiles
from circuitpy_helpers.led_animations import updateAnimationData
from circuitpy_helpers.calendar_time_helpers import timeHelper
from circuitpy_helpers.led_animations import controlLights
from circuitpy_helpers.network_helpers import wanChecker

# --- Logging --- #
logger = adafruit_logging.getLogger("trellis_lights")
logger.setLevel(adafruit_logging.INFO)

# --- Data imports --- #
try:
    from data import data
except ImportError as e:
    print(f"unable to import data: {e}")
    raise

# Variable assignments
max_brightness = data["brightness_high"]
min_brightness = data["brightness_low"]
num_pixels = data["num_pixels"]
reset_wait = data['reset_lighting_timeout']
before_sunset = data["seconds_before_sunset"]
sleep_time = data["sleep_time"]
if data["stop_time"] != 0:
    stop_time = timeHelper.get_time_in_seconds(data["stop_time"])
else:
    stop_time = int(data["stop_time"])
ignore_sunset_string = (data["ignore_sunset"])
if ignore_sunset_string is "False":
    ignore_sunset = False
else:
    ignore_sunset = True
running = False
time_in_seconds = None
sunset_in_seconds = None

# --- Pixels Configuration --- #
pixels_0 = neopixel.NeoPixel(board.SIG3, num_pixels, auto_write=False, pixel_order=neopixel.RGB)
pixels_0.brightness = max_brightness
pixels_1 = neopixel.NeoPixel(board.SIG2, num_pixels, auto_write=False, pixel_order=neopixel.RGB)
pixels_1.brightness = max_brightness

# --- MQTT Configuration --- #
radio = wifi.radio
pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)

# MQTT Feeds
subscribe_list = []
trellis_lights = os.getenv("mqtt_trellis_lights_feed")
subscribe_list.append(trellis_lights)
motion_detect = os.getenv("mqtt_motion_detect_feed")
subscribe_list.append(motion_detect)
date_time = os.getenv("mqtt_datetime_feed")
subscribe_list.append(date_time)
sunset = os.getenv("mqtt_sunset_feed")
subscribe_list.append(sunset)

# MQTT specific helpers
def on_connect(mqtt_client, userdata, flags, rc):
    # This function will be called when the mqtt_client is connected
    # successfully to the broker.
    logger.info(f"Connected to MQTT Broker {mqtt_client.broker}!")
    logger.debug(f"Flags: {flags}\n RC: {rc}")
    for topic in subscribe_list:
        mqtt_client.subscribe(topic)

def on_disconnect(mqtt_client, userdata, rc):
    # This method is called when the mqtt_client disconnects
    # from the broker.
    logger.warning(f"{mqtt_client} Disconnected from MQTT Broker!")
    counter = 0
    backoff_sleep = 1
    backoff_increment = 1
    while counter <= 10:
        try:
            mqtt_client.reconnect()
            counter = 11
        except MMQTTException:
            counter += 1
            if counter - 1 == 0:
                time.sleep(backoff_sleep)
            else:
                backoff_sleep += backoff_increment
                time.sleep(backoff_sleep)
            pass

def on_subscribe(mqtt_client, userdata, topic, granted_qos):
    # This method is called when the mqtt_client subscribes to a new feed.
    logger.info(f"Subscribed to {topic} with QOS level {granted_qos}")

def on_unsubscribe(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client unsubscribes from a feed.
    logger.info(f"Unsubscribed from {topic} with PID {pid}")

def on_publish(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client publishes data to a feed.
    logger.info(f"Published to {topic} with PID {pid}")

need_reload = False
def on_message(client, topic, message):
    global need_reload, time_in_seconds, sunset_in_seconds
    logger.info(f"New message for {client} on topic {topic}: {message}")
    # Support changes to the light configurations in the data.py file
    if "trellis" in topic:
        received_message = json.loads(message)
        # since the name of the name/value pair is known, use this in the MQTT message
        # it will be transformed to the actual value in the data file before calling updater.update_data_file
        search_string = received_message["search_string"]
        received_message['search_string'] = str(data[received_message["search_string"]])
        logger.info(f"received message is {received_message}")
        updated_message = json.dumps(received_message)
        logger.info(f"updated message is {updated_message}")
        updateFiles.update_data_file(updated_message, search_string)
        time.sleep(1)
        supervisor.reload()
    if "motion" in topic:
        if "1" in message:
            updateFiles.backup_and_restore("/data.py", backup=True)
            message = ({"filename": "data.py", "search_string": str(data['animations']), "new_value": "'motion_solid'"})
            updated_message = json.dumps(message)
            updateFiles.update_data_file(updated_message, "animations")
            time.sleep(1)
            supervisor.reload()
    if "time" in topic:
        time_in_seconds = timeHelper.get_time_in_seconds(message)
    if "sunset" in topic:
        sunset_in_seconds = timeHelper.get_time_in_seconds(message)

    # On start up see if it's before assigned start time and if it is sleep
    # Set that the lights are running so that future checks will direct activity
    #   to the shutdown routine instead
    # blank all strands prior to sending shutdown or sleep calls
    if time_in_seconds and sunset_in_seconds:
        global running
        if not running:
            need_sleep = controlLights.check_need_sleep(time_in_seconds, sunset_in_seconds, before_sunset, ignore_sunset)
            if need_sleep:
                controlLights.blank_all(pixels_0)
                controlLights.blank_all(pixels_1)
                controlLights.sleep_before_set_time(time_in_seconds, sunset_in_seconds, before_sunset)
            running = True
        else:
            need_shutdown = controlLights.check_need_shutdown(time_in_seconds, stop_time, sunset_in_seconds, sleep_time, before_sunset)
            if need_shutdown:
                controlLights.blank_all(pixels_0)
                controlLights.blank_all(pixels_1)
                controlLights.shutdown(time_in_seconds, sunset_in_seconds, sleep_time, before_sunset)

mqtt_local_broker = os.getenv("mqtt_local_server")
mqtt_local_port = os.getenv("mqtt_local_port")
mqtt_local_username = os.getenv("mqtt_local_username")
mqtt_local_key = os.getenv("mqtt_local_key")
local_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=mqtt_local_broker
    ,port = mqtt_local_port
    ,username=mqtt_local_username
    ,password=mqtt_local_key
    ,socket_pool=pool
    ,ssl_context=ssl_context
    ,is_ssl=False
)

# Connect callback handlers for local mqtt_client
local_mqtt.on_connect = on_connect
local_mqtt.on_disconnect = on_disconnect
local_mqtt.on_subscribe = on_subscribe
local_mqtt.on_unsubscribe = on_unsubscribe
local_mqtt.on_publish = on_publish
local_mqtt.on_message = on_message

# Connect
network_status = wanChecker.cpy_wan_active()
# Only try to connect if WAN is accessible
if network_status:
    try:
        local_mqtt.connect()
    except adafruit_minimqtt.adafruit_minimqtt.MMQTTException:
        logger.error("Failed to connect to MQTT broker")
        pass
else:
    logger.error("Network not connected, did not try to connect to MQTT broker!")

# -- Build chosen animation objects -- #
chosen_animations = data["animations"]
animation_builder = animationBuilder
animation_group = []
color_choice = None
override_array = ["sparkles", "speed", "rate", "count", "period", "tail_length", "step", "reverse", "spacing",
                  "size", "bounce"]
# Read in all animations from json file
# And build the animation objects and append them to the array
with open("circuitpy_helpers/led_animations/animations.json", "r") as infile:
    adata = json.load(infile)
    for item in adata['animations']:
        if item['name'] in chosen_animations:
            # Check for any animation overrides and update the JSON object
            item_with_overrides = updateAnimationData.override_default_settings(data, override_array, item)
            # Set the color choice
            updated_item = updateAnimationData.set_color(data, item_with_overrides)
            logger.info(f"item to send is {updated_item}")
            obj_0 = animation_builder.build_animation(pixels_0, updated_item)
            obj_1 = animation_builder.build_animation(pixels_1, updated_item)
            animation_group.append(obj_0)
            animation_group.append(obj_1)

# This application is working with two LED nets, therefore if it's one animation there will still be two objects
# Therefore, if there are more than two objects, create an animation sequence with the advance interval at a value higher than 0
# Otherwise, it's one selected animation with an object for each net, so advance interval is set to 0
if len(animation_group) > 2:
    animations = AnimationSequence(
        AnimationGroup(
            *(x for x in animation_group)
            ,sync=True)
        ,advance_interval=5
    )
else:
    animations = AnimationSequence(
        AnimationGroup(
            *(x for x in animation_group)
            ,sync=True)
        ,advance_interval=0
    )

# --- Settings for Non-Blocking(ish) Hack provided by Mikey Sklar from Adafruit Forums! --- #
FRAME_DELAY = 0.01    # 100 FPS (20 ms per frame)
MQTT_POLL_EVERY = 100 # poll MQTT every 100 frames (~2 seconds at 50 FPS)
frame_counter = 0

# --- Main --- #
logger.info(f"Trellis Lights starting up")
while True:
    # start animations
    animations.animate()

    frame_counter += 1

    # Poll MQTT and do other tasks
    # Will cause a brief pause in the running animation
    if frame_counter >= MQTT_POLL_EVERY:
        # check to see if we need to reset back to normal operations
        current_animation = data['animations']
        if "motion_solid" in current_animation:
            logger.info(f"motions lights triggered, will wait {reset_wait} seconds, then reset lights")
            time.sleep(reset_wait)
            updateFiles.backup_and_restore("/data.py", restore=True)

        # check WAN state
        wan_state = wanChecker.cpy_wan_active()

        # if MQTT_POLL_EVERY criterion is met, loop mqtt for 1 second
        # Only attempt this if WAN is accessible:1
        if wan_state:
            try:
                local_mqtt.loop(timeout=1)
            except MMQTTException as e:
                print("MQTT error:", e)
                local_mqtt.disconnect()
                # optional reconnect logic here
                # We're using the on_disconnect method
                pass

        frame_counter = 0

    time.sleep(FRAME_DELAY)

