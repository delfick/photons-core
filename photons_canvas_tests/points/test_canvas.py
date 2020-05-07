# coding: spec

from photons_canvas.orientation import Orientation, reorient
from photons_canvas.points import containers as cont
from photons_canvas.points.canvas import Canvas
from photons_canvas.points.color import Color

from photons_messages import TileMessages
from photons_products import Products

from unittest import mock
import pytest


@pytest.fixture
def device():
    return cont.Device("d073d5000077", Products.LCM3_TILE.cap)


describe "Canvas":
    it "has start properties":
        canvas = Canvas()

        for attr in ("top", "left", "right", "bottom", "width", "height"):
            assert getattr(canvas, attr) is None

    it "can combine canvases", device:
        part1 = cont.Part(0, 0, 8, 8, 0, Orientation.RightSideUp, device)
        colors1 = [(i, 1, 1, 3500) for i in range(64)]

        part2 = cont.Part(1, 1, 8, 8, 0, Orientation.RotatedLeft, device)
        colors2 = reorient([(i + 100, 1, 1, 3500) for i in range(64)], Orientation.RotatedRight)

        combined = Canvas()
        combined.add_parts((part1, colors1), (part2, colors2))

        one = Canvas()
        one.add_parts((part1, colors1))

        two = Canvas()
        two.add_parts((part2, colors2))

        made = Canvas.combine(one, two)

        assert sorted(combined.parts) == sorted(made.parts)
        assert sorted(combined.pairs()) == sorted(made.pairs())

        assert sorted([c.hue for _, c in made.pairs()]) == sorted(
            [*[i for i in range(64)], *[i + 100 for i in range(64)]]
        )

    describe "getting and setting a point":
        it "can get None if it's not in the canvas":
            c = Canvas()
            assert c[1, 2] is None
            assert c[cont.Point(1, 2)] is None

        it "can get the color from the canvas":
            c = Canvas()

            color = Color(1, 1, 1, 3500)
            c[1, 2] = color
            assert c[1, 2] is color
            assert c[cont.Point(1, 2)] is color

            assert c[2, 1] is None
            assert c[cont.Point(2, 1)] is None

        it "converts tuples to color instances on access":
            c = Canvas()

            color = (200, 1, 0.5, 3500)
            c[1, 2] = color
            assert c.points[1, 2] is color

            got = c[1, 2]
            assert isinstance(got, Color)
            assert got == Color(200, 1, 0.5, 3500)

            assert c[1, 2] is got

        it "it updates bounds when the point is a tuple":
            c = Canvas()

            assert c.bounds == ((None, None), (None, None), (None, None))

            c[1, 2] = Color(100, 1, 0.5, 3500)
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

            c[3, 5] = Color(200, 1, 0.2, 3500)
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

            # and if point is in the canvas
            c[3, 5] = Color(200, 1, 0.2, 3500)
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

        it "it updates bounds when the point is a point object":
            c = Canvas()

            assert c.bounds == ((None, None), (None, None), (None, None))

            c[cont.Point(1, 2)] = Color(100, 1, 0.5, 3500)
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

            c[cont.Point(3, 5)] = Color(200, 1, 0.2, 3500)
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

            # and if the point is in the canvas
            c[cont.Point(3, 5)] = Color(200, 1, 0.2, 3500)
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

    describe "testing inclusion":
        it "knows if a point is in the canvas":
            c = Canvas()
            assert (1, 2) not in c
            assert cont.Point(1, 2) not in c

            c[1, 2] = (200, 1, 0.2, 9000)
            assert (1, 2) in c
            assert cont.Point(1, 2) in c

            assert (2, 3) not in c
            assert cont.Point(2, 3) not in c

            c[cont.Point(2, 3)] = (100, 0.9, 0.2, 8000)
            assert (2, 3) in c
            assert cont.Point(2, 3) in c

    describe "calling the canvas":
        it "gets the value at that point":
            c = Canvas()
            c[1, 2] = (100, 1, 0, 3500)

            canvas = mock.Mock(name="canvas")
            parts = mock.Mock(name="parts")

            assert c((0, 0), canvas, parts) is None
            assert c((1, 2), canvas, parts) == Color(100, 1, 0, 3500)
            assert c(cont.Point(1, 2), canvas, parts) == Color(100, 1, 0, 3500)

    describe "getting point, color pairs":
        it "gets raw values if convert is False":
            c = Canvas()
            k1, c1 = (1, 2), (200, 1, 0, 3500)
            k2, c2 = cont.Point(3, 4), Color(100, 0, 1, 3999)

            k3, c3 = cont.Point(4, 5), (300, 0.1, 0.2, 3600)
            k4, c4 = (6, 7), Color(350, 0.8, 0.9, 3980)

            c[k1] = c1
            c[k2] = c2
            c[k3] = c3
            c[k4] = c4

            found = list(c.pairs(convert=False))
            wanted = list([(k1, c1), (k2, c2), (k3, c3), (k4, c4)])
            assert len(found) == len(wanted)

            ksf = set([k for k, _ in found])
            kwf = set([k for k, _ in wanted])
            assert len(ksf) == len(found)
            assert ksf == kwf

            for k in ksf:
                fc = [cc for kk, cc in found if kk == k][0]

                wc = None
                for wk, wc in wanted:
                    if wk == k:
                        assert wk is k
                        break

                assert fc is wc

        it "gets converted values by default":
            c = Canvas()
            k1, c1 = (1, 2), (200, 1, 0, 3500)
            k2, c2 = cont.Point(3, 4), Color(100, 0, 1, 3999)

            k3, c3 = cont.Point(4, 5), (300, 0.1, 0.2, 3600)
            k4, c4 = (6, 7), Color(350, 0.8, 0.9, 3980)

            c[k1] = c1
            c[k2] = c2
            c[k3] = c3
            c[k4] = c4

            found = sorted(c.pairs())
            wanted = sorted(
                [(cont.Point(*k1), Color(*c1)), (k2, c2), (k3, Color(*c3)), (cont.Point(*k4), c4),]
            )

            assert found == wanted
            assert all(isinstance(k, cont.Point) for k, _ in found)
            assert all(isinstance(c, Color) for _, c in found)

    describe "cloning":
        it "can clone and copy over points and parts":
            c = Canvas()

            clone = c.clone()
            assert clone.bounds == ((None, None), (None, None), (None, None))
            assert not clone.points
            assert not clone._parts
            assert clone.points is not c.points
            assert clone._parts is not c._parts

            c[1, 2] = Color(200, 1, 1, 3500)
            c[3, 5] = Color(200, 1, 1, 3500)
            assert c.bounds == ((1, 3), (5, 2), (2, 3))

            clone = c.clone()
            assert clone.bounds == ((1, 3), (5, 2), (2, 3))
            assert all(clone[k] == c[k] for k in c.points)
            assert all(cp is clp for cp, clp in zip(c._parts, clone._parts))
            assert clone.points is not c.points
            assert clone._parts is not c._parts

    describe "Making color object":
        it "passes into Color":
            c = Canvas()
            assert c.color(1, 1, 0, 3500) == Color(1, 1, 0, 3500)
            assert c.color(200, 0, 1, 9000) == Color(200, 0, 1, 9000)

    describe "getting bounds":
        it "returns Nones when no points":
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

        it "returns bounds when we have points":
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            c[1, 2] = (200, 1, 1, 3450)
            assert c.bounds == ((1, 1), (2, 2), (0, 0))

            c[cont.Point(10, 20)] = Color(100, 0, 1, 3999)
            assert c.bounds == ((1, 10), (20, 2), (9, 18))

            c[cont.Point(5, 5)] = Color(100, 0, 1, 3999)
            assert c.bounds == ((1, 10), (20, 2), (9, 18))

            c[2, 400] = Color(100, 0, 1, 3999)
            assert c.bounds == ((1, 10), (400, 2), (9, 398))

    describe "Adding parts":
        it "can add part without colors", device:
            c = Canvas()

            part1 = cont.Part(0, 2, 8, 9, 1, Orientation.RightSideUp, device)
            c.add_parts(part1)

            assert c.bounds == ((0, 8), (16, 7), (8, 9))
            assert c.parts == [part1]
            assert list(c.pairs()) == []

        it "can add a part with colors", device:
            c = Canvas()

            part1 = cont.Part(0, 2, 8, 9, 1, Orientation.RightSideUp, device)
            colors1 = [(i + 20, 1, 0, 3500) for i in range(64)]
            c.add_parts((part1, colors1))

            assert c.bounds == ((0, 8), (16, 7), (8, 9))
            assert c.parts == [part1]

            points = list(c.pairs())
            assert len(set(k for k, _ in points)) == len(points) == 64

            assert all(point in c for point, _ in points)
            assert all(list(c.parts_for_point(point)) == [part1] for point, _ in points)

        it "can add multiple parts":
            c = Canvas()

            part1 = cont.Part(-1, 3, 7, 10, 2, Orientation.RightSideUp, device)

            part2 = cont.Part(0, 2, 8, 9, 1, Orientation.RightSideUp, device)
            colors2 = [(i + 20, 1, 0, 3500) for i in range(72)]
            assert len(part2.points) == 72

            c.add_parts(part1, (part2, colors2))

            assert c.bounds == ((-8, 8), (24, 7), (16, 17))

            assert set(k for k, _ in c.pairs()) == set(part2.points)
            assert all(list(c.parts_for_point(point)) == [part2] for point, _ in c.pairs())

            assert all(point not in c for point in part1.points)
            assert all(point in c for point in part2.points)

            assert [c[point] for point in part2.points] == colors2

    describe "updating bounds":
        it "does nothing if no parts are provided":
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            c.update_bounds([])
            assert c.bounds == ((None, None), (None, None), (None, None))

        it "updates bounds from tuples":
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            c.update_bounds([((1, 3), (10, 6), (2, 4))])
            assert c.bounds == ((1, 3), (10, 6), (2, 4))

            c.update_bounds([((1, 10), (8, 7), (7, 3))])
            assert c.bounds == ((1, 10), (10, 6), (9, 4))

            c.update_bounds([((0, 2), (0, -2), (2, 2))])
            assert c.bounds == ((0, 10), (10, -2), (10, 12))

            c.update_bounds([(12, 5)])
            assert c.bounds == ((0, 12), (10, -2), (12, 12))

            c.update_bounds([(-1, -3)])
            assert c.bounds == ((-1, 12), (10, -3), (13, 13))

            c.update_bounds([(2, 12)])
            assert c.bounds == ((-1, 12), (12, -3), (13, 15))

            c.update_bounds([(0, 13), (13, 5), (-3, -7)])
            assert c.bounds == ((-3, 13), (13, -7), (16, 20))

        it "updates bounds from objects with bounds on them", device:
            c = Canvas()
            assert c.bounds == ((None, None), (None, None), (None, None))

            P = cont.Point
            M = lambda h, v, s: mock.Mock(name="thing", bounds=(h, v, s), spec=["bounds"])

            part1 = cont.Part(1 / 8, 10 / 8, 2, 4, 1, Orientation.RightSideUp, device)

            c.update_bounds([part1])
            assert c.bounds == ((1, 3), (10, 6), (2, 4))

            c.update_bounds([M((1, 10), (8, 7), (7, 3))])
            assert c.bounds == ((1, 10), (10, 6), (9, 4))

            c.update_bounds([M((0, 2), (0, -2), (2, 2))])
            assert c.bounds == ((0, 10), (10, -2), (10, 12))

            c.update_bounds([P(12, 5)])
            assert c.bounds == ((0, 12), (10, -2), (12, 12))

            c.update_bounds([P(-1, -3)])
            assert c.bounds == ((-1, 12), (10, -3), (13, 13))

            c.update_bounds([P(2, 12)])
            assert c.bounds == ((-1, 12), (12, -3), (13, 15))

            c.update_bounds([P(0, 13), P(13, 5), P(-3, -7)])
            assert c.bounds == ((-3, 13), (13, -7), (16, 20))

    describe "parts and devices for point":
        it "can find the parts for each point":
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

            testcases = [
                ((1, 6), [a], [device1]),
                ((1, 5), [a], [device1]),
                ((1, 4), [a], [device1]),
                ((1, 3), [d], [device1]),
                ((1, 2), [d], [device1]),
                ((1, 1), [], []),
                #
                ((2, 6), [a, b], [device1, device2]),
                ((2, 5), [a, b], [device1, device2]),
                ((2, 4), [a], [device1]),
                ((2, 3), [d], [device1]),
                ((2, 2), [d], [device1]),
                ((2, 1), [], []),
                #
                ((3, 6), [a, b], [device1, device2]),
                ((3, 5), [a, b], [device1, device2]),
                ((3, 4), [a], [device1]),
                ((3, 3), [d], [device1]),
                ((3, 2), [d], [device1]),
                ((3, 1), [], []),
                #
                ((4, 6), [a], [device1]),
                ((4, 5), [a], [device1]),
                ((4, 4), [a], [device1]),
                ((4, 3), [d, e], [device1]),
                ((4, 2), [d, e], [device1]),
                ((4, 1), [e], [device1]),
                #
                ((5, 6), [], []),
                ((5, 5), [], []),
                ((5, 4), [], []),
                ((5, 3), [e], [device1]),
                ((5, 2), [e], [device1]),
                ((5, 1), [e], [device1]),
            ]

            canvas = Canvas()
            canvas.add_parts(a, b, d, e)

            for point, parts, devices in testcases:
                assert sorted(canvas.parts_for_point(point)) == sorted(parts), point
                assert sorted(canvas.devices_for_point(point)) == sorted(devices), point

            assert len(testcases) == 5 * 6

    describe "making messages":
        it "uses the message maker":
            m1 = mock.Mock(name="m1")
            m2 = mock.Mock(name="m2")
            maker = mock.Mock(name="maker", spec=["msgs"])
            maker.msgs.return_value = [m1, m2]
            FakeMsgMaker = mock.Mock(name="MsgMaker", return_value=maker, spec=[])

            layer1 = mock.Mock(name="layer1")
            layer2 = mock.Mock(name="layer2")

            c = Canvas()

            with mock.patch("photons_canvas.points.canvas.MsgMaker", FakeMsgMaker):
                assert list(c.msgs(layer1, layer2)) == [m1, m2]

            FakeMsgMaker.assert_called_once_with(c)
            maker.msgs.assert_called_once_with(
                (layer1, layer2), average=False, acks=False, duration=1, randomize=False
            )

            acks = mock.Mock(name="acks")
            average = mock.Mock(name="average")
            duration = mock.Mock(name="duration")
            randomize = mock.Mock(name="randomize")

            FakeMsgMaker.reset_mock()
            maker.msgs.reset_mock()

            with mock.patch("photons_canvas.points.canvas.MsgMaker", FakeMsgMaker):
                assert list(
                    c.msgs(
                        layer1,
                        layer2,
                        average=average,
                        acks=acks,
                        randomize=randomize,
                        duration=duration,
                    )
                ) == [m1, m2]

            FakeMsgMaker.assert_called_once_with(c)
            maker.msgs.assert_called_once_with(
                (layer1, layer2), average=average, acks=acks, duration=duration, randomize=randomize
            )

        it "generates Set64 messages for tiles":
            c = Canvas()

            device1 = cont.Device("d073d5000077", Products.LCM3_TILE.cap)
            device2 = cont.Device("d073d5000088", Products.LCM3_TILE.cap)

            c.add_parts(cont.Part(0, 0, 8, 8, 0, Orientation.RightSideUp, device1))
            c.add_parts(cont.Part(1, 1, 8, 8, 1, Orientation.RightSideUp, device2))
            c.add_parts(cont.Part(0, 0, 8, 8, 1, Orientation.RightSideUp, device1))

            msgs = sorted(c.msgs(), key=lambda m: (m.target, m.tile_index))
            assert all(m | TileMessages.Set64 for m in msgs)

            assert msgs[0].serial == device1.serial
            assert msgs[0].tile_index == 0

            assert msgs[1].serial == device1.serial
            assert msgs[1].tile_index == 1

            assert msgs[2].serial == device2.serial
            assert msgs[2].tile_index == 1
