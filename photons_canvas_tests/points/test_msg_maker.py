# coding: spec

from photons_canvas.points.msg_maker import MsgMaker
from photons_canvas.orientation import Orientation
from photons_canvas.points import containers as cont
from photons_canvas.points.canvas import Canvas

from photons_messages import TileMessages
from photons_messages.fields import Color
from photons_products import Products

from unittest import mock
import pytest

describe "MsgMaker":
    it "asks for the color for all the points":
        # 6   a c c a _
        # 5   a c c a _
        # 4   a a a a _
        # 3   d d d f e
        # 2   d d d f e
        # 1   _ _ _ e e
        #
        # 0   1 2 3 4 5

        # a = (1, 6) -> (4, 4)
        # b = (2, 6) -> (3, 5)
        # c = a + b

        # d = (1, 3) -> (4, 2)
        # e = (4, 3) -> (5, 1)
        # f = d + e

        O = Orientation.RightSideUp

        device1 = cont.Device("d073d5000077", Products.LCM3_TILE.cap)
        device2 = cont.Device("d073d5000088", Products.LCM3_TILE.cap)

        # Part = user_x, user_y, width, height, part_number, orientation, device
        a = cont.Part(1 / 8, 6 / 8, 4, 3, 2, O, device1)
        b = cont.Part(2 / 8, 6 / 8, 2, 2, 1, O, device2)
        d = cont.Part(1 / 8, 3 / 8, 4, 2, 1, 1, device1)
        e = cont.Part(4 / 8, 3 / 8, 2, 3, 3, 1, device1)

        canvas = Canvas()
        canvas.add_parts(a, b, d, e)

        a_points = [
            (1, 6),
            (2, 6),
            (3, 6),
            (4, 6),
            (1, 5),
            (2, 5),
            (3, 5),
            (4, 5),
            (1, 4),
            (2, 4),
            (3, 4),
            (4, 4),
        ]

        b_points = [(2, 6), (3, 6), (2, 5), (3, 5)]

        d_points = [(1, 3), (2, 3), (3, 3), (4, 3), (1, 2), (2, 2), (3, 2), (4, 2)]

        e_points = [(4, 3), (5, 3), (4, 2), (5, 2), (4, 1), (5, 1)]

        maker = MsgMaker(canvas)

        color_called = []
        ls = mock.Mock(name="layers")
        avg = mock.Mock(name="average")

        def _color(point, layers, *, average=False):
            assert layers is ls
            assert average is avg
            color_called.append(tuple(point))
            return f"P({tuple(point)})"

        _color = mock.Mock(name="_color", side_effect=_color)

        m1 = mock.Mock(name="m1")
        m2 = mock.Mock(name="m2")
        m3 = mock.Mock(name="m3")
        m4 = mock.Mock(name="m4")
        m5 = mock.Mock(name="m5")
        m6 = mock.Mock(name="m6")
        m7 = mock.Mock(name="m7")
        m8 = mock.Mock(name="m8")

        results = {a: [m1, m2], b: [m3, m4], d: [m5, m6], e: [m7, m8]}

        msg_called = []

        def msgs(s, cs, **kwargs):
            msg_called.append((s, cs))
            return results[s]

        acks = mock.Mock(name="acks")
        duration = mock.Mock(name="duration")
        randomize = mock.Mock(name="randomize")

        with mock.patch.object(maker, "_color", _color), mock.patch.object(cont.Part, "msgs", msgs):
            got = list(
                maker.msgs(ls, average=avg, acks=acks, duration=duration, randomize=randomize)
            )
            assert got == [m1, m2, m3, m4, m5, m6, m7, m8]

        # 30 points, only 6 have no part
        # We want to make sure points aren't resolved more than once
        assert len(color_called) == 24
        assert set(color_called) == set([*a_points, *b_points, *d_points, *e_points])

        assert msg_called == [
            (a, [f"P({p})" for p in a_points]),
            (b, [f"P({p})" for p in b_points]),
            (d, [f"P({p})" for p in d_points]),
            (e, [f"P({p})" for p in e_points]),
        ]

    it "yields Set64 messages for tiles":
        O = Orientation.RightSideUp
        device1 = cont.Device("d073d5000077", Products.LCM3_TILE.cap)
        a = cont.Part(1 / 8, 6 / 8, 4, 3, 2, O, device1)

        canvas = Canvas()
        assert len(a.points) == 12
        canvas.add_parts((a, ((i, 1, 1, 3500) for i in range(12))))

        msgs = list(MsgMaker(canvas).msgs([]))
        assert len(msgs) == 1

        msg = msgs[0]

        assert msg | TileMessages.Set64
        assert msg.duration == 1
        assert not msg.ack_required
        assert not msg.res_required
        assert msg.serial == device1.serial

        assert msg.colors == [Color(i, 1, 1, 3500) for i in range(12)] + [Color(0, 0, 0, 0)] * (
            64 - 12
        )

    describe "getting colors":

        @pytest.fixture()
        def device(self):
            return cont.Device("d073d5000077", Products.LCM3_TILE.cap)

        @pytest.fixture()
        def part1(self, device):
            O = Orientation.RightSideUp
            return cont.Part(1 / 8, 6 / 8, 4, 3, 2, O, device)

        @pytest.fixture()
        def part2(self, device):
            O = Orientation.RightSideUp
            return cont.Part(2 / 8, 6 / 8, 2, 2, 1, O, device)

        @pytest.fixture()
        def maker(self, part1, part2):
            canvas = Canvas()
            assert len(part1.points) == 12
            canvas.add_parts((part1, ((i, 1, 1, 3500) for i in range(12))), part2)
            return MsgMaker(canvas)

        it "gets from the canvas if there are no layers", maker:
            maker.canvas.points[(1, 2)] = "POINT"
            assert maker._color((1, 2), []) == "POINT"
            assert maker._color((-1, -2), []) is None

        it "gets from layers till one is found", maker, part1, part2:
            called = []

            def layer1(point, canvas, parts):
                called.append(("layer1", point))
                assert canvas is maker.canvas
                assert isinstance(point, cont.Point)
                if parts == [part1]:
                    return f"P1{tuple(point)}"
                elif parts == [part1, part2]:
                    return
                else:
                    assert parts == []

            def layer2(point, canvas, parts):
                called.append(("layer2", point))
                if parts == [part1, part2]:
                    return f"COMBINED{tuple(point)}"
                else:
                    assert parts == []

            layer3 = Canvas()
            layer3[(-1, -2)] = "NEG"
            layer3[(1, 6)] = "NEG2"

            def final_layer(point, canvas, parts):
                called.append(("final_layer", point))
                if point == (-3, -4):
                    return "CATCH"

            layers = [layer1, layer2, layer3, final_layer]

            assert maker._color(cont.Point(2, 6), layers) == "COMBINED(2, 6)"
            assert maker._color(cont.Point(1, 6), layers) == "P1(1, 6)"
            assert maker._color(cont.Point(3, 6), layers) == "COMBINED(3, 6)"
            assert maker._color(cont.Point(4, 6), layers) == "P1(4, 6)"
            assert maker._color(cont.Point(-1, -2), layers) == "NEG"
            assert maker._color(cont.Point(-3, -4), layers) == "CATCH"
            assert maker._color(cont.Point(10, 9), layers) is None

        it "can average colors", maker:

            def layer1(point, canvas, parts):
                if point == (1, 2):
                    return (1, 1, 1, 3500)
                elif point == (3, 4):
                    return (10, 1, 0, 3500)

            def layer2(point, canvas, parts):
                if point == (3, 4):
                    return (20, 0.1, 0.4, 3500)

            layer3 = Canvas()
            layer3[(3, 4)] = (30, 0.2, 0.8, 9000)
            layer3[(1, 2)] = (40, 0.5, 0.9, 7000)

            def layer4(point, canvas, parts):
                if point == (5, 6):
                    return (100, 1, 0, 3500)

            layers = [layer1, layer2, layer3, layer4]

            assert maker._color(cont.Point(1, 2), layers, average=True) == (
                20.499999999999996,
                0.75,
                0.95,
                5250,
            )
            assert maker._color(cont.Point(3, 4), layers, average=True) == (
                19.999999999999996,
                0.43333333333333335,
                0.4000000000000001,
                5333,
            )
            assert maker._color(cont.Point(5, 6), layers, average=True) == (100, 1, 0, 3500)
            assert maker._color(cont.Point(7, 8), layers, average=True) is None
