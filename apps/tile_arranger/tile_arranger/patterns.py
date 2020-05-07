from photons_canvas import CanvasColor

import itertools
import random


class Black:
    pass


class Patterns:
    def __init__(self):
        self.styles = iter(self.compute_styles())

    def make_color(self, hue, dim=False):
        if hue in (None, Black):
            c = CanvasColor(0, 0, 0, 3500)
        else:
            c = CanvasColor(hue, 1, 0.5, 3500)

        if c.saturation == 1:
            if not dim:
                c.brightness = 1
            else:
                c.brightness = dim

        return c

    def compute_styles(self):
        colors = [0, 50, 100, 180, 250, 300]
        options = list(self.options(colors))
        random.shuffle(options)

        os = iter(itertools.cycle(options))

        while True:
            nxt = next(os)
            for sp in nxt:
                yield sp

    def options(self, colors):
        shifted = colors[2:] + colors[:2]

        yield [("color", (color,)) for color in colors]
        yield [("split", (color,)) for color in colors]

        for attr in ("x", "cross", "dot", "hourglass"):
            yield [(attr, (color,)) for color in colors]
            if attr != "x":
                if attr != "dot":
                    yield [(attr, (Black, color)) for color in colors]
                yield [(attr, (h1, h2)) for h1, h2 in zip(colors, shifted)]

    def set_canvas(self, canvas, coord):
        typ, options = next(self.styles)
        getattr(self, f"set_{typ}")(canvas, coord, *options)

        _, (top_y, _), _ = coord.bounds
        for (i, j) in coord.points:
            if j == top_y + 1:
                canvas[(i, j)] = CanvasColor(0, 0, 1, 3500)

    def set_color(self, canvas, coord, hue):
        for (i, j) in coord.points:
            canvas[(i, j)] = self.make_color(hue, dim=0.5)

    def set_split(self, canvas, coord, hue):
        (left_x, _), (top_y, _), (width, height) = coord.bounds

        for (i, j) in coord.points:
            h = Black
            if i > left_x + width / 2:
                h = hue

            canvas[(i, j)] = self.make_color(h, dim=0.5)

    def quadrants(self, canvas, coord):
        """
        Split the tile into quadrants and return information such that if you
        fill out one quadrant, the others will be the same but mirrored/flipped.

        yields (row, column), set_points

        Where set_points takes in a color to set for all the quadrants
        """
        (left_x, _), (top_y, _), (width, height) = coord.bounds

        all_is = set()
        all_js = set()

        for (i, j) in coord.points:
            all_is.add(i)
            all_js.add(j)

        sorted_is = sorted(all_is)
        sorted_js = sorted(all_js)

        is_from_left, is_from_right = (
            sorted_is[len(sorted_is) // 2 :],
            list(reversed(sorted_is[: len(sorted_is) // 2])),
        )

        js_from_bottom, js_from_top = (
            sorted_js[len(sorted_js) // 2 :],
            list(reversed(sorted_js[: len(sorted_js) // 2])),
        )

        def make_point_setter(points):
            def set_points(color):
                for point in points:
                    canvas[point] = color

            return set_points

        for column, (left_i, right_i) in enumerate(zip(is_from_left, is_from_right)):
            for row, (bottom_j, top_j) in enumerate(zip(js_from_bottom, js_from_top)):
                points = [
                    (left_i, top_j),
                    (right_i, top_j),
                    (left_i, bottom_j),
                    (right_i, bottom_j),
                ]

                yield (row, column), make_point_setter(points)

    def set_cross(self, canvas, coord, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or t else False)

        for (row, column), set_points in self.quadrants(canvas, coord):
            if row == 0 or column == 0:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_x(self, canvas, coord, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or not t else False)

        for (row, column), set_points in self.quadrants(canvas, coord):
            s = row * 2 + 2
            if row == s and column == s or column + 1 == row or row + 1 == column:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_hourglass(self, canvas, coord, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.3 if h is Black or not t else False)

        for (row, column), set_points in self.quadrants(canvas, coord):
            s = column * 2 - 2
            if row >= s and column >= s:
                set_points(make_color(False))
            else:
                set_points(make_color(True))

    def set_dot(self, canvas, coord, hue1, hue2=None):
        def make_color(t):
            h = [hue1, hue2][t]
            return self.make_color(h, dim=0.5 if h is Black or t else False)

        for (row, column), set_points in self.quadrants(canvas, coord):
            s = row * 2
            if column == s and row >= s:
                set_points(make_color(False))
            else:
                set_points(make_color(True))
