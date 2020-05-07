#!/usr/bin/python -ci=__import__;o=i("os");s=i("sys");a=s.argv;p=o.path;y=p.join(p.dirname(a[1]),".python");o.execv(y,a)

from photons_canvas.animations import Animation, Finish, AnimationRunner
from photons_canvas.canvas import CanvasColor

from photons_app.executor import library_setup
from photons_app.special import FoundSerials

from delfick_project.logging import setup_logging
from delfick_project.norms import dictobj
import logging
import random

log = logging.getLogger("tile_animation")


class Options(dictobj.Spec):
    pass


class State:
    def __init__(self, coords):
        self.color = CanvasColor(random.randrange(0, 360), 1, 1, 3500)

        self.wait = 0
        self.filled = {}
        self.remaining = {}

        for coord in coords:
            for point in coord.points:
                self.remaining[point] = True

    def progress(self):
        next_selection = random.sample(list(self.remaining), k=min(len(self.remaining), 10))

        for point in next_selection:
            self.filled[point] = True
            del self.remaining[point]


class Animation(Animation):
    coords_straight = True

    def setup(self):
        """This method can be used to do any extra setup for all tiles under the animation"""

    async def process_event(self, event):
        """
        This is called for each event related to the running of the animation

        It takes in and event object which has a number of properties on it

        value
            A value associated with the event

        coords
            The Coords object with rearranged co-ordinates of the devices

        real_coords
            The Coords object with the co-ordinates set on the devices

        canvas
            The current canvas object used to paint the tiles with

        devices
            A list of the devices this animation is operating on

        animation
            The current animation object

        background
            The background object used to provide pixels not set on your canvas

        state
            The current state associated with your animation. You can set a new
            state by using ``event.state = new_state``. This new_state will be
            the event.state for the next event

        is_tick
            Is this event a TICK event. This is determined by the animation's
            ``every`` property which is the number of seconds between creating
            a new canvas to paint on the devices. It defaults to 0.075 seconds.

            This event is special and the only one where the return value of
            this function is used. If you want a new canvas to be painted onto
            the devices, you return a Canvas object. Events after this will
            have the last Canvas that was returned. If you don't want new
            values to be painted then return None from this event

            This event will only be used if there are one or more devices used
            by this animation.

        is_error
            For when some error was encountered. The ``value`` is the exception
            that was caught.

        is_end
            When the animation has ended

        is_start
            When the animation has started

        is_user_event
            It's possible to create events yourself and this event happens
            when those are created. It's ``value`` is the event you created.

        is_new_device
            When a device has been added to the animation. The ``value`` is
            the device object that was added.

        is_sent_messagse
            When the animation sends messages to the devices. The ``value`` for
            this event are the Set64 messages that were sent
        """
        if not event.is_tick:
            return

        if event.state is None:
            event.state = State(event.coords)

        event.state.progress()

        if not event.state.remaining:
            self.acks = True
            event.state.wait += 1

        if event.state.wait == 2:
            self.every = 1
            self.duration = 1

        if event.state.wait == 3:
            raise Finish("Transition complete")

        color = event.state.color
        if event.state.wait > 1:
            color = CanvasColor(0, 0, 0, 3500)

        for point in event.state.filled:
            event.canvas[point] = color

        return event.canvas


async def doit(collector):
    # Get the object that can talk to the devices over the lan
    lan_target = collector.configuration["target_register"].resolve("lan")

    # reference can be a single d073d5000001 string representing one device
    # Or a list of strings specifying multiple devices
    # Or a special reference like we have below
    # More information on special references can be found at
    # https://delfick.github.io/photons-core/photons_app/special.html#photons-app-special
    reference = FoundSerials()

    # Options for our animations
    # The short form used here is a list of animations to run
    # We are saying only animation to run.
    # We provide the Animation class and the Options class associated with that animation
    # The "as_start" says the canvas given to us will start with the current
    #   colors on the devices
    # The last argument is options to create the Options object with.
    run_options = [[(Animation, Options), "as_start", None]]

    def error(e):
        log.error(e)

    # And now we run the animation using an AnimationRunner
    photons_app = collector.configuration["photons_app"]
    try:
        with photons_app.using_graceful_future() as final_future:
            async with lan_target.session() as sender:
                runner = AnimationRunner(
                    sender,
                    reference,
                    run_options,
                    final_future=final_future,
                    message_timeout=1,
                    error_catcher=error,
                )
                await runner.run()
    except Finish:
        pass


if __name__ == "__main__":
    # Setup the logging
    setup_logging()

    # setup photons and get back the configuration
    collector = library_setup()

    # Run the animation!
    collector.run_coro_as_main(doit(collector))
