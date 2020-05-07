# coding: spec

from photons_canvas.points import helpers as php, containers as cont
from photons_canvas.points.color import Color

from unittest import mock
import pytest


describe "hsbk":
    it "converts None":
        assert php.hsbk(None) == (0, 0, 0, 0)

    it "converts a tuple":
        assert php.hsbk((100, 1, 1, 3500)) == (100, 1, 1, 3500)

    it "converts canvas color":
        assert php.hsbk(Color(200, 1, 0, 9000)) == (200, 1, 0, 9000)

    it "converts a dictionary":
        assert php.hsbk({"hue": 300, "saturation": 1, "brightness": 0, "kelvin": 7000}) == (300, 1, 0, 7000)

    it "converts from attribute access otherwise":
        c = mock.Mock(name="color", hue=360, saturation=0, brightness=0.5, kelvin=3000, spec=["hue", "saturation", "brightness", "kelvin"])
        assert php.hsbk(c) == (360, 0, 0.5, 3000)

describe "average_color":

    def assertColorAlmostEqual(self, got, want):
        got = Color(*got)
        want = Color(*want)
        assert want.hue == pytest.approx(got.hue, rel=1e-3)
        assert want.saturation == pytest.approx(got.saturation, rel=1e-3)
        assert want.brightness == pytest.approx(got.brightness, rel=1e-3)
        assert want.kelvin == pytest.approx(got.kelvin, rel=1e-3)

    it "returns None if no colors":
        color = php.average_color([])
        assert color is None

        color = php.average_color([None])
        assert color is None

    it "averages saturation, brightness and kelvin":
        colors = [
            (0, 0.1, 0.2, 3500),
            (0, 0.2, 0.3, 4500),
            (0, 0.3, 0.4, 5500),
        ]

        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (0, 0.2, 0.3, 4500))

    it "it sets kelvin to 3500 if 0":
        colors = [
            (0, 0.1, 0.2, 3500),
            (0, 0.2, 0.3, 0),
            (0, 0.3, 0.4, 3500),
        ]

        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (0, 0.2, 0.3, 3500))

    it "does special math to the hue":
        #
        # NOTE: I'm not sure how to test this maths so I've just put these values into the algorithm
        #       and asserting the results I got back.
        #

        colors = [(hue, 1, 1, 3500) for hue in (10, 20, 30)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (19.9999, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 20, 30)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (48.2227, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 20, 30, 300)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (24.2583, 1, 1, 3500))

        colors = [(hue, 1, 1, 3500) for hue in (100, 300)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (20, 1, 1, 3500))

        colors = [(100, 1, 1, 3500), None, (300, 1, 1, 3500)]
        color = php.average_color(colors)
        self.assertColorAlmostEqual(color, (20, 1, 1, 3500))

describe "Points":
    it "can get points for a row":
        bounds = ((3, 8), (5, 1), (5, 4))
        row = list(php.Points.row(3, bounds))
        assert all(isinstance(c, cont.Point) for c in row)
        assert row == [(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)]

    it "can get points for a column":
        bounds = ((3, 8), (5, 1), (5, 4))
        col = list(php.Points.col(2, bounds))
        assert all(isinstance(c, cont.Point) for c in col)
        assert col == [(2, 5), (2, 4), (2, 3), (2, 2)]

    it "can get rows":
        bounds = ((3, 8), (5, 1), (5, 4))
        rows = list(php.Points.rows(bounds))
        assert all(all(isinstance(c, cont.Point) for c in row) for row in rows)

        assert rows == [
            [(3, 5), (4, 5), (5, 5), (6, 5), (7, 5)],
            [(3, 4), (4, 4), (5, 4), (6, 4), (7, 4)],
            [(3, 3), (4, 3), (5, 3), (6, 3), (7, 3)],
            [(3, 2), (4, 2), (5, 2), (6, 2), (7, 2)],
        ]

    it "can get cols":
        bounds = ((3, 8), (5, 1), (5, 4))
        cols = list(php.Points.cols(bounds))
        assert all(all(isinstance(c, cont.Point) for c in col) for col in cols)

        assert cols == [
            [(3, 5), (3, 4), (3, 3), (3, 2)],
            [(4, 5), (4, 4), (4, 3), (4, 2)],
            [(5, 5), (5, 4), (5, 3), (5, 2)],
            [(6, 5), (6, 4), (6, 3), (6, 2)],
            [(7, 5), (7, 4), (7, 3), (7, 2)],
        ]

    it "can get all":
        bounds = ((3, 8), (5, 1), (5, 4))
        all_points = list(php.Points.all_points(bounds))
        assert all(isinstance(c, cont.Point) for c in all_points)

        # fmt: off
        assert all_points == [
            (3, 5), (4, 5), (5, 5), (6, 5), (7, 5),
            (3, 4), (4, 4), (5, 4), (6, 4), (7, 4),
            (3, 3), (4, 3), (5, 3), (6, 3), (7, 3),
            (3, 2), (4, 2), (5, 2), (6, 2), (7, 2),
        ]
        # fmt: off

    it "can expand a bounds":
        bounds = ((3, 8), (5, 1), (5, 4))

        assert php.Points.expand(bounds, 5) == ((-2, 13), (10, -4), (15, 14))
        assert php.Points.expand(bounds, 3) == ((0, 11), (8, -2), (11, 10))
