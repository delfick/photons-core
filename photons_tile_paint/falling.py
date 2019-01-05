from photons_tile_paint.animation import Animation, Finish
from photons_tile_paint.options import AnimationOptions
from photons_themes.theme import ThemeColor as Color
from photons_themes.canvas import Canvas

from input_algorithms.errors import BadSpecValue
from input_algorithms.dictobj import dictobj
from input_algorithms import spec_base as sb
import random
import math

class TileFallingOptions(AnimationOptions):
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)

    line_tip_hue = dictobj.Field(sb.integer_spec, default=40)
    line_body_hue = dictobj.Field(sb.integer_spec, default=90)

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration

class Line:
    def __init__(self, column, rate, state, head_color, body_color):
        self.state = state
        self.position = state.top
        self.column = column
        self.rate = rate
        self.head_color = head_color
        self.body_color = body_color

    @property
    def done(self):
        return self.position < self.state.bottom

    def draw(self, canvas):
        closeness = 1.0 - (self.position - math.floor(self.position))
        head_color = Color.copy(self.head_color)
        head_color.brightness = closeness
        middle_color = Color.copy(self.head_color)
        middle_color.hue = middle_color.hue + (self.body_color.hue - middle_color.hue) * closeness
        canvas[(self.column, math.floor(self.position))] = head_color
        canvas[(self.column, math.floor(self.position) + 1)] = middle_color
        canvas[(self.column, math.floor(self.position) + 2)] = Color.copy(self.body_color)

    def progress(self):
        self.position -= self.rate

class TileFallingState:
    def __init__(self, coords, options):
        self.options = options

        self.coords = coords

        self.left = min(left for (left, top), (width, height) in coords)
        self.right = max(left + width for (left, top), (width, height) in coords)
        self.top = max(top for (left, top), (width, height) in coords)
        self.bottom = min(top - height for (left, top), (width, height) in coords)

        self.lines = []
        self.canvas = Canvas()
        for x in range(self.left, self.right):
            for y in range(self.bottom, self.top):
                self.canvas[(x, y)] = Color(0, 1, 0, 3500)

        self.line_color = Color(options.line_tip_hue, 1, 1, 3500)
        self.body_color = Color(options.line_body_hue, 1, 1, 3500)

    def tick(self):
        # 25% chance of adding a new line tis tick
        if random.randrange(0, 100) < 25 or len(self.lines) <= 3:
            # Make a new line in a random column, with a random speed
            column = random.randint(self.left, self.right - 1)
            if not any(l.column == column for l in self.lines):
                self.lines.append(
                    Line(
                        column=column,
                        rate=(random.randrange(10, 30) + 10) / 100,
                        state=self,
                        head_color=self.line_color,
                        body_color=self.body_color,
                    )
                )

        for line in self.lines:
            line.progress()

        # Cleanup any finished lines
        if any(line.done for line in self.lines):
            self.lines = [line for line in self.lines if not line.done]

        return self

    def make_canvas(self):
        # Dim existing pixels
        for pixel in self.canvas.points.values():
            if pixel.brightness > 0:
                pixel.brightness = max(0, pixel.brightness - 0.1)
        # Now draw new line ends
        for line in self.lines:
            line.draw(self.canvas)
        return self.canvas

class TileFallingAnimation(Animation):
    def setup(self):
        self.iteration = 0

    def next_state(self, prev_state, coords):
        if prev_state is None:
            return TileFallingState(coords, self.options)

        self.iteration += 1
        if self.options.final_iteration(self.iteration):
            raise Finish("Reached max iterations")

        return prev_state.tick()

    def make_canvas(self, state, coords):
        return state.make_canvas()
