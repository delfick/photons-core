from photons_canvas.animations.features.marquee.animation import (
    MarqueeAnimation,
    MarqueeDirection,
    Options,
)
from photons_canvas.animations import an_animation
from photons_canvas.font import Character

from photons_canvas.canvas import CanvasColor


class Options(Options):
    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.direction = MarqueeDirection.RIGHT

    @property
    def text_width(self):
        return 11


class NyanCharacter(Character):
    colors = {
        "c": CanvasColor(207, 0.47, 0.14, 3500),  # cyan
        "y": CanvasColor(60, 1, 0.11, 3500),  # yellow
        "w": CanvasColor(0, 0, 0.3, 3500),  # white
        "p": CanvasColor(345, 0.25, 0.12, 3500),  # pink
        "o": CanvasColor(24, 1, 0.07, 3500),  # orange
        "r": CanvasColor(0, 1, 0.15, 3500),  # red
        "b": CanvasColor(240, 1, 0.15, 3500),  # blue
        "g": CanvasColor(110, 1, 0.15, 3500),  # green
    }


Nyan1 = NyanCharacter(
    """
        ___________
        _oo________
        oyyoorppwpw
        yggywpppbwb
        gccggpppwww
        c__ccrpppr_
        ______w__w_
        ___________
    """
)

Nyan2 = NyanCharacter(
    """
        ___________
        ___________
        o__oorpppr_
        yooyypppwpw
        gyygwpppbwb
        cggccrppwww
        _cc__w__w__
        ___________
    """
)


@an_animation("nyan", Options)
class NyanAnimation(MarqueeAnimation):
    """Make nyan go back and forth across your tiles"""

    def characters(self, state):
        if state.x % 6 in (0, 1, 2):
            return [Nyan1]
        else:
            return [Nyan2]
