from photons_canvas.font import alphabet_8, alphabet_16, put_characters_on_canvas
from photons_canvas.animations import Animation, Finish, an_animation
from .options import Options, MarqueeDirection

from photons_canvas.canvas import Canvas


@an_animation("marquee", Options)
class MarqueeAnimation(Animation):
    """Print scrolling text to the tiles"""

    every = 0.075
    acks = False
    duration = 0
    switch_directions = False
    coords_vertically_aligned = True

    def setup(self):
        self.iteration = 0

    class State:
        def __init__(self, x, make_characters):
            self.x = x
            self.make_characters = make_characters
            self.characters = make_characters(self)

        def move_left(self, amount):
            self.x -= amount
            self.characters = self.make_characters(self)
            return self

        def move_right(self, amount):
            self.x += amount
            self.characters = self.make_characters(self)
            return self

        @property
        def text_width(self):
            return sum(ch.width for ch in self.characters)

    def maybe_switch(self, event):
        if self.switch_directions:
            if self.options.direction is MarqueeDirection.LEFT:
                self.options.direction = MarqueeDirection.RIGHT
                return self.next_state_right(event)
            else:
                self.options.direction = MarqueeDirection.LEFT
                return self.next_state_left(event)
        else:
            if event.state is None:
                event.state = self.next_state_left(event)
            return event.state

    def next_state_left(self, event):
        _, _, (width, _) = event.coords.bounds

        if event.state is None:
            event.state = self.State(width, self.characters)

        elif event.state.x < -event.state.text_width:
            self.iteration += 1
            if self.options.final_iteration(self.iteration):
                raise Finish("Reached max iterations")
            event.state = None
            self.maybe_switch(event)
        else:
            event.state = event.state.move_left(getattr(self.options, "speed", 1))

        return event.state

    def next_state_right(self, event):
        _, _, (width, _) = event.coords.bounds

        if event.state is None:
            event.state = self.State(0, self.characters)
            event.state.move_left(event.state.text_width)

        elif event.state.x > width:
            self.iteration += 1
            if self.options.final_iteration(self.iteration):
                raise Finish("Reached max iterations")
            event.state = None
            self.maybe_switch(event)
        else:
            event.state = event.state.move_right(getattr(self.options, "speed", 1))

        return event.state

    def characters(self, state):
        characters = []
        for ch in self.options.text:
            if getattr(self.options, "large_font", False):
                characters.append(alphabet_16[ch])
            else:
                characters.append(alphabet_8[ch])
        return characters

    async def process_event(self, event):
        if not event.is_tick:
            return

        if self.options.direction is MarqueeDirection.LEFT:
            self.next_state_left(event)
        else:
            self.next_state_right(event)

        canvas = Canvas()

        def modify_point(point):
            return point[0] + event.state.x, point[1]

        put_characters_on_canvas(
            canvas,
            self.characters(event.state),
            event.coords,
            self.options.text_color.color,
            modify_point=modify_point,
        )

        return canvas
