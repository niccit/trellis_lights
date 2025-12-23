# SPDX-License-Identifier: MIT
import json
import os
import time
import wifi
import board
import neopixel
import adafruit_connection_manager
import adafruit_minimqtt.adafruit_minimqtt
from adafruit_minimqtt.adafruit_minimqtt import MMQTTException
from adafruit_led_animation.group import AnimationGroup
from adafruit_led_animation.sequence import AnimationSequence
import onMessageTasks
import buildTrellisAnimations
from circuitpy_helpers.file_helpers import updateFiles
# --- Data imports --- #
try:
    from data import data
except ImportError as e:
    raise
# --- Pixels Configuration --- #
pixels_0 = neopixel.NeoPixel(board.SIG1, data["num_pixels"], auto_write=False, pixel_order=neopixel.RGB, brightness=data["brightness_high"])
pixels_1 = neopixel.NeoPixel(board.SIG3, data["num_pixels"], auto_write=False, pixel_order=neopixel.RGB, brightness=data["brightness_high"])
# --- MQTT Configuration ---#
subscribe_list = [os.getenv("mqtt_trellis_lights_feed"), os.getenv("mqtt_motion_detect_feed"), os.getenv("mqtt_sleep_feed")]
pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
local_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=os.getenv("mqtt_local_server")
    ,port=os.getenv("mqtt_local_port")
    ,username=os.getenv("mqtt_local_username")
    ,password=os.getenv("mqtt_local_key")
    ,socket_pool=pool
    ,ssl_context=ssl_context
    ,is_ssl=False
)
def on_connect(mqtt_client, userdata, flags, rc):
    # This function will be called when the mqtt_client is connected
    # successfully to the broker.
    print(f"Connected to MQTT Broker {mqtt_client.broker}!")
    for topic in subscribe_list:
        mqtt_client.subscribe(topic, qos=0)
running = False
def on_message(mqtt_client, topic, message):
    global running
    print(f"New message for {mqtt_client} on topic {topic}: {message}")
    if "lights" in topic:
        onMessageTasks.trellis_lighting_call(message)
    if "motion" in topic:
        onMessageTasks.motion_detected(message)
    if "sleep" in topic:
        import json
        msg_json = json.loads(message)
        from circuitpy_helpers.led_animations import controlLights
        controlLights.blank_all(pixels_0)
        controlLights.blank_all(pixels_1)
        controlLights.sleep_before_set_time(msg_json["time_in_seconds"], msg_json["sunset_in_seconds"], msg_json["sleep_before"])
        del msg_json
    if "shutdown" in topic:
        import json
        msg_json = json.loads(message)
        from circuitpy_helpers.led_animations import controlLights
        controlLights.blank_all(pixels_0)
        controlLights.blank_all(pixels_1)
        controlLights.shutdown(msg_json["time_in_seconds"], msg_json["sunset_in_seconds"], msg_json["sleep_time"], msg_json["sleep_before"])
        del msg_json

local_mqtt.on_connect = on_connect
local_mqtt.on_message = on_message
local_mqtt.connect()
# --- Build Animations --- #
animation_group = []
obj_0 = buildTrellisAnimations.build_animations(pixels_0)
obj_1 = buildTrellisAnimations.build_animations(pixels_1)
animation_group.append(obj_0)
animation_group.append(obj_1)
if len(animation_group) > 2:
    animations = AnimationSequence(
        AnimationGroup(
            *(x for x in animation_group)
            , sync=True)
        , advance_interval=5
    )
else:
    animations = AnimationSequence(
        AnimationGroup(
            *(x for x in animation_group)
            , sync=True)
        , advance_interval=0
    )
del animation_group
# --- Settings for Non-Blocking(ish) Hack provided by Mikey Sklar from Adafruit Forums! --- #
FRAME_DELAY = 0.01    # 100 FPS (20 ms per frame)
MQTT_POLL_EVERY = 500 # poll MQTT about every 30 seconds (every 100 frames is about ~2 seconds at 50 FPS)
frame_counter = 0
# --- Main --- #
while True:
    animations.animate()
    frame_counter += 1
    if frame_counter >= MQTT_POLL_EVERY:
        current_animation = data['animations']
        if "motion_solid" in data['animations']:
            running_time = data['reset_lighting_timeout']
            updateFiles.backup_and_restore("/data.py", restore=True, sleep_time=running_time)
            del current_animation
        try:
            local_mqtt.loop(timeout=1)
        except MMQTTException as e:
            local_mqtt.reconnect()
            local_mqtt.loop(timeout=1)
            pass
        except OSError as e:
            local_mqtt.reconnect()
            local_mqtt.loop(timeout=1)
            pass
        frame_counter = 0
    time.sleep(FRAME_DELAY)


