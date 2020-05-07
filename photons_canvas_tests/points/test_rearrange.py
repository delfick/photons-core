# coding: spec

from photons_canvas.points import containers as cont
from photons_canvas.points import rearrange as rea
from photons_canvas.orientation import Orientation
from photons_canvas.points import helpers as php
from photons_canvas.points.canvas import Canvas

from photons_products import Products

from unittest import mock
import random


describe "rearrange":
    it "creates a new canvas from the parts given by the rearranger":
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

        rp1 = mock.Mock(name="rp1")
        rp2 = mock.Mock(name="rp2")

        part1 = cont.Part(0, 0, 4, 4, 1, Orientation.RightSideUp, device, real_part=rp1)
        part2 = cont.Part(1, 0.25, 4, 4, 2, Orientation.RightSideUp, device, real_part=rp2)

        colors1 = [(i, 1, 1, 3500) for i in range(16)]
        colors2 = [(i, 0, 0, 3500) for i in range(16)]

        class Rearranger:
            def rearrange(s, canvas):
                for part in canvas.parts:
                    yield part, part.clone(user_x=2)

        canvas = Canvas()
        canvas.add_parts((part1, colors1), (part2, colors2))

        n = rea.rearrange(canvas, Rearranger())
        assert n is not canvas
        assert len(n.parts) == len(canvas.parts)
        assert sorted([repr(p) for p in n.parts]) == sorted([repr(p) for p in canvas.parts])

        assert sorted([p.bounds for p in n.parts]) == [
            ((16, 20), (0, -4), (4, 4)),
            ((16, 20), (2, -2), (4, 4)),
        ]

        # fmt: off
        expected = [
            (0, 0, 0, 3500), (1, 0, 0, 3500), (2, 0, 0, 3500), (3, 0, 0, 3500),
            (4, 0, 0, 3500), (5, 0, 0, 3500), (6, 0, 0, 3500), (7, 0, 0, 3500),
            (8, 0, 0, 3500), (9, 0, 0, 3500), (10, 0, 0, 3500), (11, 0, 0, 3500),
            (12, 0, 0, 3500), (13, 0, 0, 3500), (14, 0, 0, 3500), (15, 0, 0, 3500),
            (8, 1, 1, 3500), (9, 1, 1, 3500), (10, 1, 1, 3500), (11, 1, 1, 3500),
            (12, 1, 1, 3500), (13, 1, 1, 3500), (14, 1, 1, 3500), (15, 1, 1, 3500),
        ]
        # fmt: on

        assert [n[p] for p in php.Points.all_points(n.bounds)] == expected
        assert set(p.real_part for p in n.parts) == set([rp1, rp2])

    it "can create new canvas without colors":
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

        rp1 = mock.Mock(name="rp1")
        rp2 = mock.Mock(name="rp2")

        part1 = cont.Part(0, 0, 4, 4, 1, Orientation.RightSideUp, device, real_part=rp1)
        part2 = cont.Part(1, 0.25, 4, 4, 2, Orientation.RightSideUp, device, real_part=rp2)

        colors1 = [(i, 1, 1, 3500) for i in range(16)]
        colors2 = [(i, 0, 0, 3500) for i in range(16)]

        class Rearranger:
            def rearrange(s, canvas):
                for part in canvas.parts:
                    yield part, part.clone(user_x=2)

        canvas = Canvas()
        canvas.add_parts((part1, colors1), (part2, colors2))

        n = rea.rearrange(canvas, Rearranger(), keep_colors=False)
        assert n is not canvas
        assert len(n.parts) == len(canvas.parts)
        assert sorted([repr(p) for p in n.parts]) == sorted([repr(p) for p in canvas.parts])

        assert sorted([p.bounds for p in n.parts]) == [
            ((16, 20), (0, -4), (4, 4)),
            ((16, 20), (2, -2), (4, 4)),
        ]

        assert all(n[p] is None for p in php.Points.all_points(n.bounds))
        assert set(p.real_part for p in n.parts) == set([rp1, rp2])

describe "Rearrangers":

    def make_parts(self, *corner_and_sizes):
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
        for i, (user_x, user_y, width, height) in enumerate(corner_and_sizes):
            real_part = cont.Part(user_x, user_y, width, height, i, Orientation.RightSideUp, device)

            ux = random.randrange(200, 210)
            uy = random.randrange(100, 104)
            yield cont.Part(
                ux, uy, width, height, i, Orientation.RightSideUp, device, real_part=real_part
            )

    def assertParts(self, rearranger, parts, *new_corners):
        canvas = Canvas()
        canvas.add_parts(*parts)
        made = list(rearranger.rearrange(canvas))
        by_key = {repr(p): p for p in parts}

        assert len(by_key) == len(made) == len(parts) == len(new_corners)

        got = []
        for (old, new), (left_x, top_y) in zip(made, new_corners):
            assert repr(old) == repr(new)
            assert new.width == old.width
            assert new.height == old.height
            assert new.real_part is old.real_part
            got.append((new.user_x * 8, new.user_y * 8))

        assert got == list(new_corners)

    describe "Separate alignment":
        it "aligns separate user_x and leaves y alignment":
            parts = list(self.make_parts((0, 1, 8, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 8, 8)))
            self.assertParts(rea.Separate(), parts, (0, 8), (8, 16), (12, 56), (15, 32))

    describe "Straight alignment":
        it "makes all parts line up on the same y axis":
            parts = list(self.make_parts((0, 1, 7, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 20, 8)))
            self.assertParts(rea.Straight(), parts, (0, 0), (4, 0), (11, 0), (31, 0))

    describe "Vertical alignment":
        it "puts all parts at the same y level":
            parts = list(self.make_parts((0, 1, 8, 8), (-1, 2, 4, 5), (5, 7, 3, 10), (0, 4, 8, 8)))
            self.assertParts(rea.VerticalAlignment(), parts, (0, 0), (-8, 0), (40, 0), (0, 0))
