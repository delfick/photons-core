# coding: spec

from photons_canvas.points.color import Color

from unittest import mock

describe "Color":
    it "takes in hue, saturation, brightness and kelvin":
        c = Color(200, 1, 0.5, 9000)
        assert c.hue == 200
        assert c.saturation == 1
        assert c.brightness == 0.5
        assert c.kelvin == 9000

        assert repr(c) == "<Color (200,1,0.5,9000)>"

    it "can be turned into a dictionary":
        c = Color(300, 0.2, 0.1, 8000)
        assert c.is_dict
        assert c.as_dict() == {"hue": 300, "saturation": 0.2, "brightness": 0.1, "kelvin": 8000}

    it "can be cloned":
        c = Color(120, 0.2, 0.7, 7000)
        assert c.hue == 120
        assert c.saturation == 0.2
        assert c.brightness == 0.7
        assert c.kelvin == 7000

        clone = c.clone()
        assert clone.hue == 120
        assert clone.saturation == 0.2
        assert clone.brightness == 0.7
        assert clone.kelvin == 7000

        assert clone is not c

        clone.hue = 50
        clone.saturation = 0.3
        clone.brightness = 1
        clone.kelvin = 4000
        assert clone.hue == 50
        assert clone.saturation == 0.3
        assert clone.brightness == 1
        assert clone.kelvin == 4000

        assert c.hue == 120
        assert c.saturation == 0.2
        assert c.brightness == 0.7
        assert c.kelvin == 7000

    it "can be cloned with new values":
        c = Color(120, 0.2, 0.7, 7000)
        assert c.hue == 120
        assert c.saturation == 0.2
        assert c.brightness == 0.7
        assert c.kelvin == 7000

        clone = c.clone(hue=90, saturation=0, brightness=0.8, kelvin=1000)
        assert clone.hue == 90
        assert clone.saturation == 0
        assert clone.brightness == 0.8
        assert clone.kelvin == 1000

        assert clone is not c
        assert c.hue == 120
        assert c.saturation == 0.2
        assert c.brightness == 0.7
        assert c.kelvin == 7000

    it "can be used as a key in a dictionary":
        c1 = Color(120, 0.2, 0.7, 7000)
        c2 = c1.clone()

        c3 = Color(90, 0.1, 0.8, 1000)
        c4 = c3.clone(hue=100)

        d = {c1: 1, c3: 3, c4: 4}
        assert d[c1] == 1
        assert d[c2] == 1
        assert d[c3] == 3
        assert d[c4] == 4

        assert hash(c1) == hash((c1.hue, c1.saturation, c1.brightness, c1.kelvin))

        d[c1] = 5
        assert d[c1] == 5
        assert d[(120, 0.2, 0.7, 7000)] == 5

    it "can be used in equality with tuples and other colors":
        c1 = Color(120, 0.2, 0.7, 7000)
        assert c1 == (c1.hue, c1.saturation, c1.brightness, c1.kelvin)
        assert c1 != (1, c1.saturation, c1.brightness, c1.kelvin)
        assert c1 != (c1.hue, 0, c1.brightness, c1.kelvin)
        assert c1 != (c1.hue, c1.saturation, 1, c1.kelvin)
        assert c1 != (c1.hue, c1.saturation, c1.brightness, 1000)

        c2 = c1.clone()
        assert c1 == c2

        c2.hue = 2
        assert c1 != c2

        assert c1 != {}
        assert c1 is not None

        m = mock.Mock(name="other", spec=[])
        assert c1 != m

        m.hue = 120
        assert c1 != m

        m.saturation = 0.2
        assert c1 != m

        m.brightness = 0.7
        assert c1 != m

        m.kelvin = 2000
        assert c1 != m

        m.kelvin = 7000
        assert c1 == m

    it "can be turned into a tuple":
        t = tuple(Color(100, 1, 0, 3500))
        assert isinstance(t, tuple)
        assert t == (100, 1, 0, 3500)

    it "can get properties":
        c = Color(200, 0.5, 0.3, 8900)
        assert c.get("hue") == 200
        assert c.get("saturation") == 0.5
        assert c.get("brightness") == 0.3
        assert c.get("kelvin") == 8900

        assert c.get("other") is None
        assert c.get("other", "wat") == "wat"
