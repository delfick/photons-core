# coding: spec

from photons_canvas.points.color import Color as CanvasColor
from photons_canvas.points.simple_messages import Set64
from photons_canvas.points import containers as cont
from photons_canvas.orientation import Orientation

from photons_messages import LightMessages, TileMessages
from photons_messages.fields import Color
from photons_products import Products

from unittest import mock
import pytest

describe "Point":
    it "takes in information":
        point = cont.Point(1, 2)
        assert point.col == 1
        assert point.row == 2
        assert point.key == (1, 2)
        assert repr(point) == "<Point (1,2)>"

    it "equals tuples and other points":
        p1 = cont.Point(1, 2)

        assert p1 == p1
        assert p1 == cont.Point(1, 2)
        assert p1 != cont.Point(2, 1)
        assert p1 != cont.Point(3, 4)

        assert p1 == (1, 2)
        assert p1 != (3, 1)
        assert (1, 2) == p1

    it "can be used as a key in a dictionary":
        p1 = cont.Point(1, 2)
        p2 = cont.Point(1, 2)
        p3 = cont.Point(3, 4)

        d = {p1: 1, p3: 5, (5, 6): 6}
        assert d[p1] == 1
        assert d[p2] == 1
        assert d[p3] == 5

        assert d[(1, 2)] == 1
        assert d[cont.Point(5, 6)] == 6

    it "can return a bounds tuples":
        p1 = cont.Point(3, 5)
        assert p1.bounds == ((3, 3), (5, 5), (0, 0))

    it "can return itself relative to bounds":
        # (left, right), (top, bottom), (width, height)
        area = ((1, 5), (7, 3), (10, 10))

        # From left to right
        # From bottom to top
        assert cont.Point(2, 5).relative(area) == (1, 2)
        assert cont.Point(1, 3).relative(area) == (0, 4)
        assert cont.Point(5, 7).relative(area) == (4, 0)

describe "Part":

    @pytest.fixture
    def V(self):
        class V:
            device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)

        return V()

    it "takes in some properties", V:
        user_x = 2
        user_y = 3
        width = 5
        height = 10
        part_number = 5
        orientation = Orientation.RightSideUp
        real_part = mock.Mock(name="real_part", spec=[])
        original_colors = mock.Mock(name="original_colors", spec=[])

        part = cont.Part(
            user_x,
            user_y,
            width,
            height,
            part_number,
            orientation,
            V.device,
            real_part=real_part,
            original_colors=original_colors,
        )

        assert part.device is V.device
        assert part.real_part is real_part
        assert part.original_colors is original_colors
        assert part.orientation is orientation
        assert part.part_number == part_number
        assert part.random_orientation in Orientation.__members__.values()

        assert part.user_x == user_x
        assert part.user_y == user_y
        assert part.width == width
        assert part.height == height

        assert part.left == (2 * 8)
        assert part.right == (2 * 8) + 5

        assert part.top == 3 * 8
        assert part.bottom == (3 * 8) - 10

    it "can update position", V:
        part = cont.Part(2, 3, 4, 5, 1, Orientation.RightSideUp, V.device)
        assert part.bounds == ((16, 20), (24, 19), (4, 5))

        part.update(5, 6, 7, 8)
        assert part.bounds == ((40, 47), (48, 40), (7, 8))

    it "can clone", V:
        cloned = mock.Mock(name="cloned_part", spec=[])
        FakePart = mock.Mock(name="FakePart", return_value=cloned)

        real_part = mock.Mock(name="real_part", spec=[])
        original_colors = mock.Mock(name="original_colors", spec=[])

        oa = (0, Orientation.RightSideUp, V.device)
        okw = {"real_part": real_part, "original_colors": original_colors}

        part = cont.Part(2, 3, 4, 5, *oa, **okw)

        with mock.patch("photons_canvas.points.containers.Part", FakePart):
            assert part.clone() is cloned
            FakePart.assert_called_once_with(2, 3, 4, 5, *oa, **okw)
            FakePart.reset_mock()

            assert part.clone(user_x=20) is cloned
            FakePart.assert_called_once_with(20, 3, 4, 5, *oa, **okw)
            FakePart.reset_mock()

            assert part.clone(user_x=21, user_y=30) is cloned
            FakePart.assert_called_once_with(21, 30, 4, 5, *oa, **okw)
            FakePart.reset_mock()

            assert part.clone(user_x=22, user_y=31, width=40) is cloned
            FakePart.assert_called_once_with(22, 31, 40, 5, *oa, **okw)
            FakePart.reset_mock()

            assert part.clone(user_x=23, user_y=32, width=41, height=50) is cloned
            FakePart.assert_called_once_with(23, 32, 41, 50, *oa, **okw)
            FakePart.reset_mock()

    it "returns bounds information", V:
        part = cont.Part(2, 3, 6, 7, 1, Orientation.RightSideUp, V.device)
        assert part.left == 16
        assert part.right == 22
        assert part.top == 24
        assert part.bottom == 17
        assert part.width == 6
        assert part.height == 7
        assert part.bounds == ((16, 22), (24, 17), (6, 7))

    it "hashes as serial and part number":
        part = cont.Part(
            2,
            3,
            6,
            7,
            21,
            Orientation.RightSideUp,
            cont.Device("d073d5001337", Products.LCM3_TILE.cap),
        )
        part2 = cont.Part(
            1,
            2,
            3,
            4,
            21,
            Orientation.UpsideDown,
            cont.Device("d073d5001337", Products.LCM3_TILE.cap),
        )

        d = {part: 1}
        assert d[part] == 1
        assert d[part2] == 1
        assert d[("d073d5001337", 21)] == 1

        assert ("d073d5001337", 0) not in d
        assert ("d073d5001338", 1) not in d

    it "can equal other parts and tuples":
        part1 = cont.Part(
            2,
            3,
            6,
            7,
            21,
            Orientation.RightSideUp,
            cont.Device("d073d5001337", Products.LCM3_TILE.cap),
        )

        part2 = part1.clone()

        part3 = cont.Part(
            1,
            2,
            3,
            4,
            21,
            Orientation.UpsideDown,
            cont.Device("d073d5001337", Products.LCM3_TILE.cap),
        )

        part4 = cont.Part(
            2,
            3,
            6,
            7,
            0,
            Orientation.RightSideUp,
            cont.Device("d073d5001338", Products.LCM3_TILE.cap),
        )

        assert part1 == part2
        assert part2 == part3
        assert part1 == part3
        assert part1 != part4

        assert part1 == ("d073d5001337", 21)
        assert part1 != ("d073d5001338", 21)
        assert part1 != ("d073d5001337", 1)

    it "can reverse orient", V:
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])

        oa = (0, Orientation.RotatedLeft, V.device)
        part = cont.Part(2, 3, 4, 5, *oa)

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reverse_orient(colors) is ret_colors

        reorient.assert_called_once_with(colors, Orientation.RotatedRight)

    it "can orient", V:
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])

        oa = (0, Orientation.RotatedLeft, V.device)
        part = cont.Part(2, 3, 4, 5, *oa)

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reorient(colors) is ret_colors

        reorient.assert_called_once_with(colors, Orientation.RotatedLeft)

    it "can orient with random orientation", V:
        ret_colors = mock.Mock(name="ret_colors", spec=[])
        reorient = mock.Mock(name="reorient", return_value=ret_colors)

        colors = mock.Mock(name="colors", spec=[])

        oa = (0, Orientation.RotatedLeft, V.device)

        i = 0
        while i < 10:
            part = cont.Part(2, 3, 4, 5, *oa)
            if part.random_orientation is not part.orientation:
                break
            i += 1

        assert part.random_orientation is not part.orientation

        with mock.patch("photons_canvas.points.containers.reorient", reorient):
            assert part.reorient(colors, randomize=True) is ret_colors

        reorient.assert_called_once_with(colors, part.random_orientation)

    it "has a repr":
        device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
        RL = Orientation.RotatedLeft
        part = cont.Part(2, 3, 4, 5, 7, RL, device)
        assert repr(part) == "<Part (d073d5001337,7)>"

    describe "msgs":
        it "yields a SetLightPower if power_on is True":
            lcm2_cap = Products.LCM2_Z.cap(2, 80)
            assert lcm2_cap.has_extended_multizone

            for cap in (
                Products.LCM3_TILE.cap,
                Products.LCM1_Z.cap,
                lcm2_cap,
                Products.LCM2_A19.cap,
            ):
                device = cont.Device("d073d5001337", cap)
                part = cont.Part(2, 3, 4, 5, 0, Orientation.RotatedLeft, device)

                c1 = (100, 1, 1, 3500)

                msgs = list(part.msgs([c1], power_on=False))
                assert not msgs[0] | LightMessages.SetLightPower

                msgs = list(part.msgs([c1], power_on=True))
                assert msgs[0] | LightMessages.SetLightPower
                assert msgs[0].serial == device.serial
                assert msgs[0].level == 65535
                assert msgs[0].duration == 1

                msgs = list(part.msgs([c1], power_on=True, duration=100))
                assert msgs[0] | LightMessages.SetLightPower
                assert msgs[0].serial == device.serial
                assert msgs[0].level == 65535
                assert msgs[0].duration == 100

        it "returns a SetColor for bulbs":
            device = cont.Device("d073d5001337", Products.LCM2_A19.cap)
            part = cont.Part(2, 3, 4, 5, 0, Orientation.RotatedLeft, device)

            for colors in ([(100, 1, 0.4, 2400)], [CanvasColor(100, 1, 0.4, 2400)]):
                msgs = list(part.msgs(colors, duration=100))
                assert len(msgs) == 1
                assert msgs[0] | LightMessages.SetColor
                assert (
                    msgs[0].payload
                    == LightMessages.SetColor(
                        hue=100, saturation=1, brightness=0.4, kelvin=2400, duration=100
                    ).payload
                )

        it "returns multizone messages for strips":
            colors = mock.Mock(name="colors", spec=[])
            duration = mock.Mock(name="duration", spec=[])

            lcm2_cap = Products.LCM2_Z.cap(2, 80)
            assert lcm2_cap.has_extended_multizone

            m1 = mock.Mock(name="m1")
            m2 = mock.Mock(name="m2")

            maker = mock.Mock(name="maker", spec=["msgs"], msgs=[m1, m2])
            FakeMultizoneMessagesMaker = mock.Mock(name="message maker", return_value=maker)

            with mock.patch(
                "photons_canvas.points.containers.MultizoneMessagesMaker",
                FakeMultizoneMessagesMaker,
            ):
                for cap in (lcm2_cap, Products.LCM1_Z.cap):
                    device = cont.Device("d073d5001337", cap)
                    part = cont.Part(2, 3, 4, 5, 0, Orientation.RotatedLeft, device)

                    assert list(part.msgs(colors, duration=duration)) == [m1, m2]

                    FakeMultizoneMessagesMaker.assert_called_once_with(
                        device.serial, cap, colors, duration=duration
                    )
                    FakeMultizoneMessagesMaker.reset_mock()

        it "returns special Set64 message for a tile":
            colors = [(i, 1, 1, 3500) for i in range(64)]

            device = cont.Device("d073d5001337", Products.LCM3_TILE.cap)
            part = cont.Part(2, 3, 4, 5, 21, Orientation.RotatedLeft, device)

            rotated = part.reorient(colors)
            assert rotated != colors

            msgs = list(part.msgs(colors, duration=200))
            assert len(msgs) == 1
            assert msgs[0] | TileMessages.Set64
            assert msgs[0].serial == device.serial

            dct = {
                "x": 0,
                "y": 0,
                "length": 1,
                "tile_index": 21,
                "colors": [Color(*c) for c in rotated],
                "ack_required": False,
                "width": 4,
                "duration": 200,
                "res_required": False,
            }

            for k, v in dct.items():
                assert getattr(msgs[0], k) == v

            assert isinstance(msgs[0], Set64)

describe "Device":
    it "has serial, cap and width":
        serial = "d073d5001337"
        cap = Products.LCM3_TILE.cap

        device = cont.Device(serial, cap)
        assert device.serial == serial
        assert device.cap is cap

        assert repr(device) == "<Device (d073d5001337,LCM3_TILE)>"

    it "can be used as a key in a dictionary":
        device1 = cont.Device("d073d5001337", None)
        device2 = cont.Device("d073d5001337", None)
        device3 = cont.Device("d073d5001338", None)

        d = {device1: 3, device3: 5, "d073d5001339": 20}
        assert d[device1] == 3
        assert d[device2] == 3
        assert d[device3] == 5
        assert d[cont.Device("d073d5001339", None)] == 20

    it "can be compared":
        device1 = cont.Device("d073d5001337", None)
        device2 = cont.Device("d073d5001337", None)
        device3 = cont.Device("d073d5001338", None)

        assert device1 == device2
        assert device1 == "d073d5001337"

        assert device1 != device3
        assert device1 != "d073d5004556"
