from photons_canvas.animations.features.marquee.animation import (
    MarqueeAnimation,
    MarqueeDirection,
    Options,
)
from photons_canvas.animations import an_animation
from . import font


class Options(Options):
    pass


@an_animation("pacman", Options)
class TilePacmanAnimation(MarqueeAnimation):
    """Make pacman go back and forth across your tiles"""

    switch_directions = True
    coords_vertically_aligned = True

    class RightCharacters:
        def __init__(self, x):
            self.x = x

        @property
        def characters(self):
            return [
                self.pacman,
                font.Space(2),
                font.Ghost,
                font.Space(2),
                font.Ghost,
                font.Space(2),
                font.Ghost,
                font.Space(2),
                font.Ghost,
            ]

        @property
        def pacman(self):
            if self.x % 4 < 2:
                return font.PacmanL2ROpen
            else:
                return font.PacmanClosed

    class LeftCharacters:
        def __init__(self, x):
            self.x = x

        @property
        def characters(self):
            return [
                self.pacman,
                font.Space(2),
                font.Blinky,
                font.Space(2),
                font.Pinky,
                font.Space(2),
                font.Inky,
                font.Space(2),
                font.Clyde,
            ]

        @property
        def pacman(self):
            if self.x % 4 < 2:
                return font.PacmanR2LOpen
            else:
                return font.PacmanClosed

    def characters(self, state):
        if self.options.direction is MarqueeDirection.LEFT:
            return self.LeftCharacters(state.x).characters
        else:
            return self.RightCharacters(state.x).characters
