# SPDX-License-Identifier: MIT

# Normally this would be in the code.py file, however, the file was too large
# for the Sparkle Motion board to stable
# Call this method to build and return the objects
try:
    from data import data
except ImportError:
    print(f"unable to load data")
    raise

# Read in all animations from json file
# And build the animation objects and append them to the array
# Due to memory constraints on the Sparkle Motion, do not allow substitutions on speed, bounce, etc.
# A custom animations.json is used to set the values for the size of the project
def build_animations(pixels):
    import json
    import gc
    from circuitpy_helpers.led_animations import animationBuilder, updateAnimationData
    chosen_animations = data["animations"]
    with open("sparkle_motion_animations.json", "r") as infile:
        adata = json.load(infile)
        for item in adata['animations']:
            if item['name'] in chosen_animations:
                # Set the color choice
                updated_item = updateAnimationData.set_color(data, item)
                obj = animationBuilder.build_animation(pixels, updated_item)
        del adata, updated_item
        infile.close()
        gc.collect()
        return obj