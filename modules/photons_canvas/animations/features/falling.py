from photons_canvas.animations import Animation, an_animation
from photons_canvas.animations.lines import LineOptions
from photons_canvas import point_helpers as php

from delfick_project.norms import dictobj, sb
import random


class Options(LineOptions):
    min_speed = dictobj.Field(sb.float_spec, default=1)
    max_speed = dictobj.Field(sb.float_spec, default=2)


class Line:
    def __init__(self, line, rate, start, blank, tail):
        self.line = line
        self.tail = tail
        self.rate = rate
        self.start = start
        self.blank = blank

    @classmethod
    def make(kls, options, top_y):
        rate = -options.rate()
        blank = random.randrange(0, 100) < 50
        tail = random.randrange(10, 15)
        line = options.make_line(random.randrange(3, 6))
        start = top_y + random.randrange(6, 10)
        return Line(line, rate, start, blank, tail)

    def pixels(self, col, onto):
        self.line.progress(self.rate)
        pixels = list(self.line.pixels(self.start, reverse=True))

        top = None
        for row, color in pixels:
            top = row
            if self.blank:
                color = None
            onto[(col, row)] = color

        return top


class State:
    def __init__(self, options):
        self.done = {}
        self.lines = {}
        self.rates = {}
        self.start = {}
        self.options = options

    def add_cols(self, canvas):
        for point in php.Points.row(0, canvas.bounds):
            col = point[0]
            if col not in self.lines:
                self.lines[col] = []

    def next_layer(self, bounds):
        _, (top_y, bottom_y), _ = bounds

        pixels = {}

        for col, lines in list(self.lines.items()):
            remove = []

            most_top = None
            for line in lines:
                top = line.pixels(col, pixels)
                if most_top is None or top > most_top:
                    most_top = top

                if top < bottom_y:
                    remove.append(line)

            self.lines[col] = [l for l in self.lines[col] if l not in remove]

            if most_top is None or top_y - most_top > random.randrange(3, 7):
                self.lines[col].append(Line.make(self.options, top_y))

        self.done.update(pixels)

        def layer(point, canvas):
            p1 = pixels.get(point)
            p2 = canvas.points.get(point)
            if not p1 and not p2:
                return
            elif p1 and not p2:
                return p1
            elif p2 and not p1:
                if point not in self.done:
                    return p2
                else:
                    return canvas.dim(point, self.options.fade_amount)
            else:
                c = canvas.dim(point, self.options.fade_amount)
                if not c:
                    return p1

                return php.average_color([p1, c])

        return layer


@an_animation("falling", Options)
class FallingAnimation(Animation):
    def setup(self):
        self.duration = self.every

    async def process_event(self, event):
        if not event.state:
            event.state = State(self.options)

        if event.is_new_device:
            event.state.add_cols(event.canvas)
            return

        elif event.is_tick:
            return event.state.next_layer(event.canvas.bounds)
