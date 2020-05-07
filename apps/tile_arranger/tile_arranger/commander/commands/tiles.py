from tile_arranger.commander.store import store

from delfick_project.norms import dictobj, sb, BadSpecValue

import binascii
import logging
import asyncio
import sys

log = logging.getLogger("tile_arranger.commander.commands.tiles")


@store.command(name="tiles/store")
class TilesStore(store.Command):
    tasks = store.injected("tasks")
    arranger = store.injected("arranger")
    progress_cb = store.injected("progress_cb")

    async def execute(self, messages):
        self.progress_cb({"instruction": "started"}, do_log=False)

        async with self.arranger.add_stream(self.progress_cb):
            # Make sure the arranger is running
            self.tasks.add(self.arranger.run())

            async for message in messages:
                try:
                    await message.process()
                except asyncio.CancelledError:
                    raise
                except:
                    kwargs = {}
                    if hasattr(message.command, "error_reason"):
                        try:
                            kwargs["reason"] = message.command.error_reason
                        except:
                            log.exception("Failed to determine error reason")

                    self.progress_cb(sys.exc_info()[1], **kwargs)


class serial_spec(sb.Spec):
    def normalise_filled(self, meta, val):
        val = sb.string_spec().normalise(meta, val)
        if len(val) != 12:
            raise BadSpecValue("serial must be 12 characters long", got=len(val))

        try:
            binascii.unhexlify(val)
        except binascii.Error:
            raise BadSpecValue("serial must be a hex value")

        return val


@store.command(name="highlight", parent=TilesStore)
class Highlight(store.Command):
    arranger = store.injected("arranger")

    serial = dictobj.Field(serial_spec, wrapper=sb.required)
    tile_index = dictobj.Field(sb.integer_spec, wrapper=sb.required)

    async def execute(self):
        await self.arranger.add_highlight(self.serial, self.tile_index)


@store.command(name="change_coords", parent=TilesStore)
class ChanegCoords(store.Command):
    arranger = store.injected("arranger")

    serial = dictobj.Field(serial_spec, wrapper=sb.required)
    tile_index = dictobj.Field(sb.integer_spec, wrapper=sb.required)

    left_x = dictobj.Field(sb.integer_spec, wrapper=sb.required)
    top_y = dictobj.Field(sb.integer_spec, wrapper=sb.required)

    async def execute(self):
        await self.arranger.change_coords(self.serial, self.tile_index, self.left_x, self.top_y)
