from photons_tile_paint.options import GlobalOptions
from photons_tile_paint.set_64 import set_64_maker

from photons_app.errors import PhotonsAppError, TimedOut
from photons_app import helpers as hp

from photons_messages import LightMessages, DeviceMessages, Services
from photons_themes.coords import user_coords_to_pixel_coords
from photons_themes.theme import ThemeColor as Color
from photons_transport.comms.result import Result
from photons_themes.canvas import Canvas
from photons_products import Products

from collections import defaultdict
import logging
import asyncio
import time

log = logging.getLogger("photons_tile_paint.animation")


class Finish(PhotonsAppError):
    pass


coords_for_horizontal_line = user_coords_to_pixel_coords(
    [[(0, 0), (8, 8)], [(1, 0), (8, 8)], [(2, 0), (8, 8)], [(3, 0), (8, 8)], [(4, 0), (8, 8)]]
)


async def tile_serials_from_reference(reference, sender):
    """
    Given a reference, return all the serials that has a ``has_matrix`` capability
    """
    serials = []

    async for pkt in sender(DeviceMessages.GetVersion(), reference):
        if pkt | DeviceMessages.StateVersion:
            if Products[pkt.vendor, pkt.product].cap.has_matrix:
                serials.append(pkt.serial)

    return serials


def canvas_to_msgs(canvas, coords, duration=1, reorient=None, acks=False):
    for i, coord in enumerate(coords):
        colors = canvas.points_for_tile(*coord[0], *coord[1])
        if reorient:
            colors = reorient(i, colors)

        yield set_64_maker(
            tile_index=i, width=coord[1][0], duration=duration, colors=colors, ack_required=acks
        )


def put_characters_on_canvas(canvas, chars, coords, fill_color=None):
    msgs = []
    for ch, coord in zip(chars, coords):
        if ch is None:
            continue

        canvas.set_all_points_for_tile(*coord[0], *coord[1], ch.get_color_func(fill_color))

    return msgs


class TileStateGetter:
    class Info:
        def __init__(self, coords, default_color):
            self.colors = []
            self.coords = coords
            self.reorient = None
            self.default_color = default_color

        @hp.memoized_property
        def default_color_func(self):
            if not self.colors:

                def get_empty(x, y):
                    return self.default_color

                return get_empty

            canvas = self.canvas

            def default_color_func(i, j):
                return canvas.get((i, j), dflt=Color(0, 0, 0, 3500))

            return default_color_func

        @property
        def canvas(self):
            canvas = Canvas()
            for i, colors in sorted(self.colors):
                coords = self.coords

                if not coords:
                    continue

                if i >= len(coords):
                    continue

                (user_x, user_y), (width, height) = coords[i]

                rows = []
                pos = 0
                for j in range(height):
                    nxt = []
                    for i in range(width):
                        nxt.append(colors[pos])
                        pos += 1
                    rows.append(nxt)

                def get_color(x, y):
                    color = rows[y][x]
                    return Color(color.hue, color.saturation, color.brightness, color.kelvin)

                canvas.set_all_points_for_tile(user_x, user_y, width, height, get_color)
            return canvas

    def __init__(self, target, sender, serials, background_option, coords=None):
        self.sender = sender
        self.target = target
        self.coords = coords
        self.serials = serials
        self.background_option = background_option

        self.info_by_serial = defaultdict(
            lambda: self.Info(self.coords, self.background_option.default_color)
        )

    @property
    def default_color_funcs(self):
        funcs = {}
        for serial in self.serials:
            funcs[serial] = self.info_by_serial[serial].default_color_func
        return funcs

    async def fill(self, random_orientations=False):
        plans_args = ["chain"]
        if self.background_option.type == "current":
            plans_args.append("colors")

        def e(error):
            log.error(error)

        plans = self.sender.make_plans(*plans_args)
        async for serial, name, info in self.sender.gatherer.gather(
            plans, self.serials, error_catcher=e
        ):
            if name == "colors":
                self.info_by_serial[serial].colors = list(enumerate(info))

            elif name == "chain":
                self.info_by_serial[serial].coords = user_coords_to_pixel_coords(
                    info["coords_and_sizes"]
                )

                def make_reorient(random_orientations, info):
                    kwargs = {}
                    if random_orientations:
                        kwargs["randomize"] = True

                    def reorient(index, colors):
                        return info["reorient"](index, colors, **kwargs)

                    return reorient

                self.info_by_serial[serial].reorient = make_reorient(random_orientations, info)


class AnimateTask:
    """
    Used to efficiently send messages to tiles

    Because this is for a tile animation, we don't need to care about retries
    or non UDP transports, and so we can bypass much of photons machinery to
    send messages as efficiently as possible
    """

    def __init__(self, sender):
        self.sender = sender
        self.transports = {}
        self.last_spawn = None

    async def check_transports(self):
        if self.last_spawn is None:
            self.last_spawn = time.time()

        if time.time() - self.last_spawn > 5:
            # Make sure the transports are still correct
            for serial, (transport, _) in list(self.transports.items()):
                self.transports[serial] = (transport, await transport.spawn(None, timeout=1))

            self.last_spawn = time.time()

    async def get_transport(self, serial):
        if serial not in self.transports:
            transport = self.sender.found[serial][Services.UDP]
            self.transports[serial] = (transport, await transport.spawn(None, timeout=1))
        return self.transports[serial]

    async def make_messages(self, msgs):
        raise NotImplementedError("Don't know how to make messages!")

    async def add(self, msgs):
        await self.check_transports()
        async for transport, t, msg in self.make_messages(msgs):
            await transport.write(t, msg.pack().tobytes(), msg)

    async def finish(self):
        pass


class FastNetworkAnimateTask(AnimateTask):
    """
    This is a version of AnimateTask that doesn't try to throttle the messages
    we send over the network
    """

    async def make_messages(self, msgs):
        for msg in msgs:
            serial = msg.serial
            msg.update(dict(source=self.sender.source, sequence=self.sender.seq(serial)))
            transport, t = await self.get_transport(serial)
            yield transport, t, msg


class NoisyNetworkAnimateTask(AnimateTask):
    """
    This is a version of AnimateTask that tries to throttle how many messages we
    send of the network.

    It is suitable for environments where there is a lot of Wifi noise.

    Essentially, for each tile, we send acks for one of the messages we send in
    this frame. We then only send more messages if we have replies for less than
    <inflight_limit> groups of acks.

    so if you have two tiles, and an inflight_limit of 2, then we will not send
    more messages until we received all both acks for more than inflight_limit
    frames.
    """

    def __init__(self, sender, *, inflight_limit, wait_timeout):
        super().__init__(sender)
        self.tasks = []
        self.wait_timeout = wait_timeout
        self.inflight_limit = inflight_limit

    async def add(self, msgs):
        self.tasks = [
            group
            for group in self.tasks
            if any(not f.done() and time.time() - t < self.wait_timeout for t, f in group.values())
        ]

        if len(self.tasks) >= self.inflight_limit:
            return

        await super().add(msgs)

    async def make_messages(self, msgs):
        ms = []
        group = {}

        for msg in msgs:
            serial = msg.serial
            transport, t = await self.get_transport(serial)
            msg.update(dict(source=self.sender.source, sequence=self.sender.seq(serial)))

            if serial not in group:
                msg.ack_required = True
                retry_options = self.sender.retry_options_for(msg, t)
                result = Result(msg, False, retry_options)
                self.sender.receiver.register(msg, result, msg)
                group[serial] = (time.time(), result)

            ms.insert(0, (transport, t, msg))

        for transport, t, msg in ms:
            yield transport, t, msg

    async def finish(self):
        ts = []
        for g in self.tasks:
            for _, f in g.values():
                f.cancel()
                ts.append(f)

        if ts:
            await asyncio.wait(ts)


class Animation:
    every = 0.075
    coords = None
    retries = False
    duration = 0
    message_timeout = 0.3
    random_orientations = False

    def __init__(self, target, sender, options, global_options=None):
        self.sender = sender
        self.target = target
        self.options = options

        if global_options is None:
            global_options = GlobalOptions.create()
        self.global_options = global_options

        if getattr(self.options, "user_coords", False) or getattr(
            self.options, "combine_tiles", False
        ):
            self.coords = None

        self.setup()

    def setup(self):
        pass

    def next_state(self, prev_state, coords):
        raise NotImplementedError()

    def make_canvas(self, state, coords):
        raise NotImplementedError()

    def set_canvas_default_color_func(self, canvas, default_color_func):
        canvas.set_default_color_func(default_color_func)

    async def animate(self, reference, final_future, pauser=None):
        def errors(e):
            log.error(e)

        def error(e):
            if not isinstance(e, TimedOut):
                log.error(e)

        if self.global_options.noisy_network:
            inflight_limit = self.global_options.inflight_limit
            log.info(hp.lc("Using noisy_network code", inflight_limit=inflight_limit))
            task = NoisyNetworkAnimateTask(
                self.sender, wait_timeout=self.message_timeout, inflight_limit=inflight_limit
            )
        else:
            task = FastNetworkAnimateTask(self.sender)

        try:
            async for msgs in self.generate_messages(reference, final_future, pauser):
                if self.retries:
                    await self.sender(msgs, message_timeout=self.every, error_catcher=error)
                else:
                    await task.add(msgs)
        finally:
            await task.finish()

    async def generate_messages(self, reference, final_future, pauser=None):
        if pauser is None:
            pauser = asyncio.Condition()

        serials = await tile_serials_from_reference(reference, self.sender)
        state = TileStateGetter(
            self.target, self.sender, serials, self.options.background, coords=self.coords
        )
        await state.fill(random_orientations=self.random_orientations)

        by_serial = {}
        for serial in serials:
            by_serial[serial] = {
                "state": None,
                "coords": tuple(state.info_by_serial[serial].coords),
            }

        log.info("Starting!")

        await self.sender(LightMessages.SetLightPower(level=65535, duration=1), serials)

        combined_coords = []
        for info in by_serial.values():
            combined_coords.extend(info["coords"])
        combined_info = {"state": None}

        start = None
        while True:
            combined_canvas = None
            if getattr(self.options, "combine_tiles", False):
                combined_state = combined_info["state"] = self.next_state(
                    combined_info["state"], combined_coords
                )
                combined_canvas = self.make_canvas(combined_state, combined_coords)

            msgs = []
            for serial, info in by_serial.items():
                coords = info["coords"]

                canvas = combined_canvas
                if canvas is None:
                    info["state"] = self.next_state(info["state"], coords)
                    canvas = self.make_canvas(info["state"], coords)

                self.set_canvas_default_color_func(
                    canvas, state.info_by_serial[serial].default_color_func
                )

                reorient = state.info_by_serial[serial].reorient
                for msg in canvas_to_msgs(
                    canvas, coords, duration=self.duration, reorient=reorient, acks=self.retries,
                ):
                    msg.target = serial
                    msgs.append(msg)

            if start is not None:
                diff = time.time() - start
                if diff < self.every:
                    await asyncio.sleep(self.every - diff)
            start = time.time()

            async with pauser:
                if final_future.done():
                    break
                yield msgs

            if final_future.done():
                break
