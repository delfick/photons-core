from tile_arranger.request_handlers.command import WSHandler
from tile_arranger.arranger import Arranger


from whirlwind.server import Server, wait_for_futures
from whirlwind.commander import Commander
from tornado.web import StaticFileHandler
import asyncio
import logging
import time

log = logging.getLogger("tile_arranger.server")


class NoCacheStaticFileHandler(StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")


class Server(Server):
    def __init__(self, final_future, store=None):
        if store is None:
            from tile_arranger.commander.store import store, load_commands

            load_commands()

        self.store = store
        self.final_future = final_future
        self.wsconnections = {}

    def tornado_routes(self):
        return [
            (
                "/v1/ws",
                WSHandler,
                {
                    "commander": self.commander,
                    "server_time": time.time(),
                    "final_future": self.final_future,
                    "wsconnections": self.wsconnections,
                },
            ),
            (
                r"/(.*)",
                NoCacheStaticFileHandler,
                {"path": self.server_options.assets.dist, "default_filename": "index.html"},
            ),
        ]

    async def setup(self, server_options, ts, sender, reference, cleaners):
        self.sender = sender
        self.cleaners = cleaners
        self.server_options = server_options

        self.tasks = ts
        self.tasks._merged_options_formattable = True
        self.cleaners.append(self.tasks.finish)

        self.arranger = Arranger(
            self.final_future, self.sender, reference, server_options.animation_options, cleaners
        )
        self.arranger._merged_options_formattable = True
        self.tasks.add(self.arranger.run())

        async def end_wsconnections():
            try:
                await asyncio.wait([self.final_future])
            finally:
                await wait_for_futures(self.wsconnections)

        self.tasks.add(end_wsconnections())

        self.commander = Commander(
            self.store,
            tasks=self.tasks,
            arranger=self.arranger,
            final_future=self.final_future,
            server_options=self.server_options,
        )

    async def cleanup(self):
        try:
            await wait_for_futures(self.wsconnections)
        except asyncio.CancelledError:
            raise
        except:
            log.exception("Problem cleaning up websocket connections")
