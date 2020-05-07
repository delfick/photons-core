from tile_arranger.colors import convert_K_to_RGB
from tile_arranger.patterns import Patterns

from photons_app import helpers as hp

from photons_canvas.animations import Animation, AnimationRunner
from photons_messages import TileMessages
from photons_canvas import Coord

from delfick_project.norms import dictobj, sb
import colorsys
import logging
import asyncio

log = logging.getLogger("tile_arranger.arranger")


def color_to_pixels(colors):
    for c in colors:
        if c.saturation > 0:
            rgb = colorsys.hsv_to_rgb(c.hue / 360, c.saturation, c.brightness)
            rgb = tuple(int(p * 255) for p in rgb)
        else:
            if c.brightness < 0.01:
                rgb = (0, 0, 0)
            else:
                rgb = convert_K_to_RGB(c.kelvin)

        yield f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


class Options(dictobj.Spec):
    arranger = dictobj.Field(sb.any_spec, wrapper=sb.required)
    patterns = dictobj.Field(sb.any_spec, wrapper=sb.required)


class State:
    def __init__(self, canvas, options):
        self.canvas = canvas
        self.options = options
        self.arranger = self.options.arranger

        self.started = False
        self.changed = True
        self.changing = {}
        self.highlights = {}

    def add_device(self, canvas, device):
        for coord in device.coords:
            if self.started:
                self.options.patterns.set_canvas(self.canvas, coord)

    def have_stream(self, devices):
        self.changed = True
        if self.started:
            return

        self.started = True
        for device in devices:
            for coord in device.coords:
                self.options.patterns.set_canvas(self.canvas, coord)
            self.changed = True

    def add_highlight(self, serial, tile_index):
        if not self.started or (serial, tile_index) not in self.arranger.tiles_info:
            return

        key = self.arranger.tiles_info.key((serial, tile_index))
        coord = self.arranger.tiles_info.coords[key]
        self.highlights[(serial, tile_index)] = [0] + [False for _ in range(coord.height)]
        self.changed = True

    def is_changing(self, serial, tile_index):
        if not self.started:
            return
        self.changed = True
        self.changing[(serial, tile_index)] = 1

    def was_changed(self, serial, tile_index):
        if not self.started:
            return
        self.changed = True
        key = (serial, tile_index)
        if key in self.changing:
            self.changing[key] = 2

    def tick(self):
        def change_rows(rows):
            if rows[0] == 0:
                for i in range(len(rows)):
                    v = rows[i]
                    if not isinstance(v, bool):
                        continue
                    if not v:
                        rows[i] = True
                        return

            rows[0] = 1

            for i in range(len(rows) - 1, 0, -1):
                v = rows[i]
                if not isinstance(v, bool):
                    continue
                if v:
                    rows[i] = False
                    return

            rows.pop(0)

        for key, rows in list(self.highlights.items()):
            change_rows(rows)
            if not any(rows):
                del self.highlights[key]

    def make_canvas(self, devices):
        if self.changed or self.changing or self.highlights:
            self.changed = False
            canvas = self.canvas.clone()

            by_key = {}

            for device in devices:
                for coord in device.coords:
                    by_key[(coord.serial, coord.chain_index)] = coord
                    key = (coord.serial, coord.chain_index)
                    changing = self.changing.get(key)
                    if changing:
                        brightness = 0.3 + (changing / 10)
                        if self.changing[key] > 1:
                            self.changing[key] += 1
                        if brightness > 1:
                            del self.changing[key]
                            continue

                        for point in coord.points:
                            color = canvas[point].clone()
                            color.brightness = brightness
                            canvas[point] = color

            for key, rows in list(self.highlights.items()):
                rows = list(rows)
                if not isinstance(rows[0], bool):
                    rows.pop(0)

                if key not in by_key:
                    continue

                coord = by_key[key]

                for (i, j) in coord.points:
                    row = coord.top_y - j
                    if len(rows) > row:
                        if rows[row]:
                            color = canvas[(i, j)].clone()
                            color.brightness = 0
                            canvas[(i, j)] = color

            return canvas


class ArrangerAnimation(Animation):
    coords_separate = True

    def sent_messages(self, devices):
        tiles = []
        for device in devices:
            colors = device.colors
            for coord in device.real_coords:
                pixels = list(color_to_pixels(colors[coord.chain_index]))
                tiles.append(
                    (
                        {
                            "serial": coord.serial,
                            "pixels": pixels,
                            "tile_index": coord.chain_index,
                            "user_x": coord.left_x,
                            "user_y": coord.top_y,
                            "width": coord.width,
                            "height": coord.height,
                            "key": f"{coord.serial}:{coord.chain_index}",
                        },
                        coord,
                    )
                )
        self.options.arranger.tiles_info.send_instruction(tiles)

    async def process_event(self, event):
        if not event.state:
            event.state = State(event.canvas, self.options)

        if event.is_sent_messages:
            self.sent_messages(event.devices)
            return

        if event.is_new_device:
            event.state.add_device(event.canvas, event.value)
            return

        if event.is_user_event:
            value = event.value
            if value == "have_stream":
                event.state.have_stream(event.devices)
                return

            action, (serial, tile_index) = value
            lc = hp.lc.using(serial=serial, tile_index=tile_index)

            if action == "highlight":
                log.info(lc("Highlighting tile"))
                event.state.add_highlight(serial, tile_index)
            elif action == "changing":
                log.info(lc("Changing tile"))
                event.state.is_changing(serial, tile_index)
            elif action == "changed":
                event.state.was_changed(serial, tile_index)
            elif action == "have_stream":
                event.state.have_stream(event.devices)

            return

        if event.is_tick:
            event.state.tick()
            return event.state.make_canvas(event.devices)

    async def make_user_events(self, animation_state):
        async for event in self.options.arranger.arranger_events():
            yield event


class TilesInfo:
    def __init__(self, arranger):
        self.info = []
        self.all_info = []

        self.tiles = {}
        self.locks = {}
        self.pixels = {}
        self.coords = {}
        self.arranger = arranger

    def __contains__(self, key):
        return self.key(key) in self.tiles

    def send_instruction(self, tiles):
        self.update(tiles)
        for progress_cb in self.arranger.progress_cbs:
            sent = progress_cb.instructions
            try:
                if "tiles" in sent:
                    progress_cb({"instruction": "tiles", "tiles": self.info}, do_log=False)
                else:
                    progress_cb({"instruction": "tiles", "tiles": self.all_info}, do_log=False)
            except:
                log.exception("Failed to send progress")
            else:
                sent["tiles"] = True

    def update(self, tiles):
        self.info = []
        self.all_info = []

        for tile, coord in tiles:
            key = tile["key"]
            self.all_info.append(dict(tile))

            nxt = dict(tile)
            if key not in self.pixels:
                self.pixels[key] = []

            if self.pixels[key] == tile["pixels"]:
                del nxt["pixels"]

            if key not in self.tiles:
                self.tiles[key] = dict(tile)
                self.locks[key] = (asyncio.Lock(), hp.ResettableFuture())
                self.coords[key] = coord

            self.coords[key] = coord
            self.info.append(nxt)

    def key(self, key):
        if isinstance(key, tuple):
            serial, tile_index = key
            key = f"{serial}:{tile_index}"
        return key

    def coord(self, serial, tile_index):
        return self.coords.get(self.key(serial, tile_index))


class Arranger:
    def __init__(self, final_future, sender, reference, animation_options, cleaners):
        self.sender = sender
        self.cleaners = cleaners
        self.reference = reference
        self.final_future = final_future
        self.animation_options = animation_options

        self.running = False
        self.patterns = Patterns()
        self.tiles_info = TilesInfo(self)
        self.progress_cbs = []
        self.animation_fut = None
        self.events_queue = asyncio.Queue()

        self.tasks = hp.TaskHolder(self.final_future)
        self.cleaners.append(self.tasks.finish)
        self.tasks.add(self.read_events())

        self.streamer = hp.ResultStreamer(self.final_future)
        self.cleaners.append(self.streamer.finish)

    async def read_events(self):
        async for result in self.streamer:
            if result.successful:
                await self.events_queue.put(result.value)

    async def add_highlight(self, serial, tile_index):
        if (serial, tile_index) not in self.tiles_info:
            return

        async def ret():
            return "highlight", (serial, tile_index)

        await self.streamer.add_coroutine(ret())

    async def change_coords(self, serial, tile_index, left_x, top_y):
        device_key = (serial, tile_index)
        if device_key not in self.tiles_info:
            return

        si = self.tiles_info.key(device_key)
        coord_lock, fut = self.tiles_info.locks[si]
        fut.reset()
        fut.set_result((left_x, top_y))

        if coord_lock.locked():
            return

        async def gen():
            nxt = None

            async with coord_lock:
                while True:
                    key = await fut
                    if key == nxt:
                        return
                    nxt = key

                    yield "changing", (serial, tile_index)

                    coord = self.tiles_info.coords[si]
                    original = (coord.left_x, coord.top_y)

                    left_x, top_y = key
                    user_x, user_y = coord.replace_top_left(left_x, top_y)

                    msg = TileMessages.SetUserPosition(
                        tile_index=tile_index, user_x=user_x, user_y=user_y, res_required=False
                    )
                    await self.sender(msg, serial, message_timeout=2, error_catcher=[])

                    msg = TileMessages.GetDeviceChain()

                    errors = []
                    async for pkt in self.sender(
                        msg, serial, message_timeout=2, error_catcher=errors
                    ):
                        if pkt | TileMessages.StateDeviceChain:
                            if pkt.start_index == 0 and pkt.tile_devices_count > tile_index:
                                tile = pkt.tile_devices[tile_index]
                                new_left_x, new_top_y = Coord.make_left_x_top_y(
                                    tile.user_x, tile.user_y, tile.width, tile.height
                                )
                                coord.replace_top_left(new_left_x, new_top_y)
                                log.info(
                                    hp.lc(
                                        "Replaced position",
                                        serial=serial,
                                        tile_index=tile_index,
                                        user_x=tile.user_x,
                                        user_y=tile.user_y,
                                    )
                                )

                    if errors:
                        coord.replace_top_left(*original)

                    yield "changed", (serial, tile_index)

        await self.streamer.add_generator(gen())

    async def arranger_events(self):
        if self.progress_cbs:

            async def have_stream():
                return "have_stream"

            await self.streamer.add_coroutine(have_stream())

        while True:
            nxt = hp.async_as_background(self.events_queue.get())
            await asyncio.wait([nxt, self.final_future], return_when=asyncio.FIRST_COMPLETED)
            if self.final_future.done():
                nxt.cancel()
                await asyncio.wait([nxt])
                return

            yield await nxt

    def add_stream(self, progress_cb):
        async def have_stream():
            return "have_stream"

        class CM:
            async def __aenter__(s):
                log.info("Adding stream")
                self.progress_cbs.append(progress_cb)
                progress_cb.instructions = {}
                await self.streamer.add_coroutine(have_stream())

            async def __aexit__(s, exc_typ, exc, tb):
                log.info("Removing stream")
                self.progress_cbs = [pc for pc in self.progress_cbs if pc != progress_cb]
                if not self.progress_cbs and self.animation_fut:
                    self.animation_fut.cancel()

        return CM()

    async def run(self):
        if self.running or self.final_future.done():
            return

        self.running = True
        self.animation_fut = hp.ChildOfFuture(self.final_future)

        run_options = {
            "animations": [
                [
                    (ArrangerAnimation, Options),
                    "as_start",
                    {"arranger": self, "patterns": self.patterns},
                ]
            ],
            "animation_limit": 1,
            "reinstate_on_end": True,
            "reinstate_duration": 0,
        }
        try:
            log.info("Starting arranger animation")
            await AnimationRunner(
                self.sender,
                self.reference,
                run_options,
                final_future=self.animation_fut,
                message_timeout=1,
                error_catcher=lambda e: False,
                animation_options=self.animation_options,
            ).run()
        finally:
            self.running = False
            self.animation_fut = None
