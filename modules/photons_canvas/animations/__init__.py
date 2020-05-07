from photons_canvas.animations.infrastructure.register import an_animation, Animator
from photons_canvas.animations.run_options import RunOptions, make_run_options
from photons_canvas.animations.infrastructure.animation import Animation
from photons_canvas.animations.infrastructure.finish import Finish
from photons_canvas.animations.infrastructure import register
from photons_canvas.animations.runner import AnimationRunner
from photons_canvas.animations import options

import os

this_dir = os.path.dirname(__file__)

for d in ("features", "transitions"):
    for filename in os.listdir(os.path.join(this_dir, d)):
        location = os.path.join(this_dir, d, filename)
        if not filename.startswith("_") or os.path.isdir(location) or filename.endswith(".py"):
            if os.path.isfile(location):
                filename = filename[:-3]

            if d != "features" or filename in (
                "balls",
                "dice",
                "color_cycle",
                "falling",
                "time",
                "twinkles",
            ):
                __import__(f"photons_canvas.animations.{d}.{filename}")

__all__ = [
    "register",
    "an_animation",
    "AnimationRunner",
    "Animation",
    "Finish",
    "RunOptions",
    "options",
    "Animator",
    "make_run_options",
]
