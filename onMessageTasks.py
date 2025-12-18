# SPDX-License-Identifier: MIT
import json
import supervisor
import time
import gc

# All Tasks related to MQTT on-message calls
# The sparkle motion board can't open the file if it gets too big
# Putting worker methods for MQTT here

try:
    from data import data
except ImportError:
    print(f"unable to load data")
    raise

def trellis_lighting_call(message):
    from circuitpy_helpers.file_helpers import updateFiles
    received_message = json.loads(message)
    # since the name of the name/value pair is known, use this in the MQTT message
    # it will be transformed to the actual value in the data file before calling updater.update_data_file
    search_string = received_message["search_string"]
    mod_current_string = str(data[search_string]).strip("' [ ]")
    mod_new_string = str(received_message["new_value"]).strip("' [ ]")
    if mod_new_string not in mod_current_string:
        received_message['search_string'] = str(data[received_message["search_string"]])
        updated_message = json.dumps(received_message)
        updateFiles.update_data_file(updated_message, search_string)
        time.sleep(1)
        supervisor.reload()
    del received_message, mod_current_string, mod_new_string
    gc.collect()

def motion_detected(message):
    from circuitpy_helpers.file_helpers import updateFiles
    if "1" in message:
        updateFiles.backup_and_restore("/data.py", backup=True)
        message = ({"filename": "data.py", "search_string": str(data['animations']), "new_value": "'motion_solid'"})
        updated_message = json.dumps(message)
        updateFiles.update_data_file(updated_message, "animations")
        time.sleep(1)
        supervisor.reload()
    del message, updated_message
    gc.collect()