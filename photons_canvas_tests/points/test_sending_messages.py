# coding: spec

from photons_canvas import Canvas

from photons_control import test_helpers as chp
from photons_transport.fake import FakeDevice
from photons_messages.fields import Color
from photons_messages import TileMessages
from photons_products import Products

import pytest

original_a19_color = chp.Color(200, 1, 1, 3500)
original_z1_zones = [chp.Color(i, 1, 1, 3500) for i in range(50)]
original_z2_zones = [chp.Color(i + 52, 0.5, 0.5, 3500) for i in range(50)]
original_ze_zones = [chp.Color(i + 103, 0.5, 0.5, 3500) for i in range(50)]
original_tile1_pixels = [chp.Color(i + 200, 0.1, 0.2, 7000) for i in range(25)] + [
    chp.Color(0, 0, 0, 0)
] * 39
original_tile2_pixels = [chp.Color(i + 300, 0.2, 0.9, 8000) for i in range(25)] + [
    chp.Color(0, 0, 0, 0)
] * 39

a19 = FakeDevice(
    "d073d5000001", chp.default_responders(Products.LCM2_A19, color=original_a19_color)
)
z1 = FakeDevice("d073d5000002", chp.default_responders(Products.LCM1_Z, zones=original_z1_zones),)
z2 = FakeDevice("d073d5000003", chp.default_responders(Products.LCM2_Z, zones=original_z2_zones),)
ze = FakeDevice(
    "d073d5000004",
    chp.default_responders(
        Products.LCM2_Z, zones=original_ze_zones, firmware=chp.Firmware(2, 80, 0),
    ),
)
tile = FakeDevice(
    "d073d5000005",
    chp.default_responders(
        Products.LCM3_TILE,
        chain_length=2,
        chain=[
            (
                chp.TileChild.FieldSpec().empty_normalise(
                    firmware_version_major=3,
                    firmware_version_minor=70,
                    device_version_vendor=1,
                    device_version_product=55,
                    width=5,
                    height=5,
                    user_x=10 / 8,
                    user_y=20 / 8,
                ),
                original_tile1_pixels,
            ),
            (
                chp.TileChild.FieldSpec().empty_normalise(
                    firmware_version_major=3,
                    firmware_version_minor=70,
                    device_version_vendor=1,
                    device_version_product=55,
                    width=5,
                    height=5,
                    user_x=0,
                    user_y=0,
                ),
                original_tile2_pixels,
            ),
        ],
    ),
)

devices = [a19, z1, z2, ze, tile]


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner(devices) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


describe "sending messages from a canvas":

    async def make_canvas(self, runner, reference):
        plans = runner.sender.make_plans("parts_and_colors")
        canvas = Canvas()
        async for serial, _, info in runner.sender.gatherer.gather(plans, reference):
            canvas.add_parts(*[(p, p.original_colors) for p in info])

        return canvas

    async it "works for a single zone bulb", runner:
        canvas = await self.make_canvas(runner, a19.serial)
        assert len(canvas.points) == 1
        canvas[list(canvas.points)[0]] = (320, 0.8, 0.9, 5000)
        await runner.sender(list(canvas.msgs()))

        assert a19.attrs.color == chp.Color(320, 0.8, 0.9, 5000)

        await runner.sender(list(canvas.restore_msgs()))
        assert a19.attrs.color == original_a19_color

    @pytest.mark.async_timeout(2)
    async it "works for a z1 device", runner:
        canvas = await self.make_canvas(runner, z1.serial)
        assert len(canvas.points) == 50

        new_colors = [(i, 0, 0, 200) for i in range(50)]
        for point, color in zip(canvas.parts[0].points, new_colors):
            canvas[point] = color
        await runner.sender(list(canvas.msgs()))

        assert z1.attrs.zones == [chp.Color(*c) for c in new_colors]

        z1.reset_received()
        await runner.sender(list(canvas.restore_msgs()))
        assert z1.attrs.zones == original_z1_zones
        assert len(z1.received) == 50

    @pytest.mark.async_timeout(2)
    async it "works for a z2 device", runner:
        canvas = await self.make_canvas(runner, z2.serial)
        assert len(canvas.points) == 50

        new_colors = [(i, 0, 0, 200) for i in range(50)]
        for point, color in zip(canvas.parts[0].points, new_colors):
            canvas[point] = color
        await runner.sender(list(canvas.msgs()))

        assert z2.attrs.zones == [chp.Color(*c) for c in new_colors]

        z2.reset_received()
        await runner.sender(list(canvas.restore_msgs()))
        assert z2.attrs.zones == original_z2_zones
        assert len(z2.received) == 50

    async it "works for an extended multizone device", runner:
        assert chp.ProductResponder.capability(ze).has_extended_multizone

        canvas = await self.make_canvas(runner, ze.serial)
        assert len(canvas.points) == 50

        new_colors = [(i, 0, 0, 200) for i in range(50)]
        for point, color in zip(canvas.parts[0].points, new_colors):
            canvas[point] = color
        await runner.sender(list(canvas.msgs()))

        assert ze.attrs.zones == [chp.Color(*c) for c in new_colors]

        ze.reset_received()
        await runner.sender(list(canvas.restore_msgs()))
        assert ze.attrs.zones == original_ze_zones
        assert len(ze.received) == 1

    async it "works for tiles", runner:
        assert chp.ProductResponder.capability(tile).has_chain

        canvas = await self.make_canvas(runner, tile.serial)
        assert len(canvas.points) == 50
        assert len(canvas.parts) == 2

        new_colors1 = [(i, 1, 0, 3000) for i in range(25)] + [(0, 0, 0, 0)] * 39
        new_colors2 = [(i + 30, 0.9, 1, 2500) for i in range(25)] + [(0, 0, 0, 0)] * 39

        assert all(p.device.serial == tile.serial for p in canvas.parts)
        assert [p.part_number for p in canvas.parts] == [0, 1]

        for point, color in zip(canvas.parts[0].points, new_colors1):
            canvas[point] = color
        for point, color in zip(canvas.parts[1].points, new_colors2):
            canvas[point] = color

        tile.reset_received()
        await runner.sender(list(canvas.msgs()))
        assert len(tile.received) == 2

        assert all(p | TileMessages.Set64 for p in tile.received)
        assert tile.received[0].tile_index == 0
        assert tile.received[0].colors == [Color(*c) for c in new_colors1]

        assert tile.received[1].tile_index == 1
        assert tile.received[1].colors == [Color(*c) for c in new_colors2]

        new_cs_1 = [chp.Color(*c) for c in new_colors1]
        new_cs_2 = [chp.Color(*c) for c in new_colors2]

        assert tile.attrs.chain == [
            (tile.attrs.chain[0][0], new_cs_1),
            (tile.attrs.chain[1][0], new_cs_2),
        ]

        tile.reset_received()
        await runner.sender(list(canvas.restore_msgs()))
        assert tile.attrs.chain == [
            (tile.attrs.chain[0][0], original_tile1_pixels),
            (tile.attrs.chain[1][0], original_tile2_pixels),
        ]
        assert len(tile.received) == 2
        assert all(p | TileMessages.Set64 for p in tile.received)
        assert tile.received[0].source != 0
        assert tile.received[1].source != 0
