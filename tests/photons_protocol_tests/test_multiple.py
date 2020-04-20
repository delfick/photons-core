# coding: spec

from photons_protocol.errors import BadConversion
from photons_protocol.packets import dictobj
from photons_protocol.types import Type as T

from delfick_project.errors_pytest import assertRaises
from delfick_project.norms import BadSpecValue, Meta
from bitarray import bitarray
import enum
import json


def ba(val):
    b = bitarray(endian="little")
    b.frombytes(val)
    return b


def list_of_dicts(lst):
    """
    Helper to turn a list into dictionaries

    This is because depending on how an object is created, strings can be
    represented internally as either string or bitarray.

    This behaviour is due to a performance optimisation I don't want to remove
    so, I compare with normalised values instead
    """
    return [l.as_dict() for l in lst]


describe "The multiple modifier":

    def assertProperties(self, thing, checker):
        checker(thing)

        bts = thing.pack()
        thing2 = type(thing).unpack(bts)
        checker(thing2)

        thing3 = type(thing).normalise(Meta.empty(), json.loads(repr(thing)))
        checker(thing3)

    it "allows multiple of raw types and structs":

        class Other(dictobj.PacketSpec):
            fields = [("four", T.Uint32)]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("two", T.Int32.multiple(2).default(0)),
                ("three", T.Bytes(4).multiple(2, kls=Other)),
            ]

        thing = Thing(one=True, two=[1], three=[{"four": 4}, {"four": 10}])

        def test_thing(thing):
            assert thing.one == 1
            assert thing.two == [1, 0]
            assert thing.three == [Other(four=4), Other(four=10)]

        self.assertProperties(thing, test_thing)

    it "create items from nothing":

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3).default(lambda pkt: "")),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing(
            one=["MEH", E.BLAH],
            two=[1, 2, 3],
            three=["on", "two"],
            four=[{"one": False, "five": [b"1", b"t"]}, {"one": True}],
        )

        assert thing.one == [E.MEH, E.BLAH, E.ZERO]
        assert thing.two == [1, 2, 3]
        assert thing.three == ["on", "two", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b"1"), ba(b"t")]),
            Other(one=True, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        thing = Thing()
        assert thing.one == [E.ZERO, E.ZERO, E.ZERO]
        assert thing.two == [0, 0, 0]
        assert thing.three == ["", "", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

    it "allows replacing items in place":

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3)),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing(
            one=["MEH", E.BLAH],
            two=[1, 2, 3],
            three=["on", "two", "thre"],
            four=[{"one": False, "five": [b"1", b"t"]}, {"one": True}],
        )

        assert thing.one == [E.MEH, E.BLAH, E.ZERO]
        assert thing.two == [1, 2, 3]
        assert thing.three == ["on", "two", "thre"]
        assert thing.four == [
            Other(one=False, five=[ba(b"1"), ba(b"t")]),
            Other(one=True, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        thing.one[-1] = 2
        thing.two[0] = 10
        thing.three[1] = "wat"
        thing.four[2] = {"one": False, "five": [b"y"]}

        def test_replacement(thing):
            assert thing.one == [E.MEH, E.BLAH, E.BLAH]
            assert thing.two == [10, 2, 3]
            assert thing.three == ["on", "wat", "thre"]

            assert thing.four == [
                Other(one=False, five=[ba(b"1"), ba(b"t")]),
                Other(one=True, five=[ba(b""), ba(b"")]),
                Other(one=False, five=[ba(b"y"), ba(b"")]),
            ]

        self.assertProperties(thing, test_replacement)

    it "allows replacing items in place when from nothing":

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [
                ("one", T.BoolInt),
                ("five", T.Bytes(16).multiple(2).default(lambda pkt: b"")),
            ]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3).default(lambda pkt: "")),
                ("four", T.Bytes(40).multiple(3, kls=Other)),
            ]

        thing = Thing()
        assert thing.one == [E.ZERO, E.ZERO, E.ZERO]
        assert thing.two == [0, 0, 0]
        assert thing.three == ["", "", ""]
        assert thing.four == [
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
            Other(one=False, five=[ba(b""), ba(b"")]),
        ]

        thing.one[-1] = 2
        thing.two[0] = 10
        thing.three[1] = "wat"
        thing.four[2] = {"one": True, "five": [b"y"]}

        def test_replacement(thing):
            assert thing.one == [E.ZERO, E.ZERO, E.BLAH]
            assert thing.two == [10, 0, 0]
            assert thing.three == ["", "wat", ""]
            assert thing.four == [
                Other(one=False, five=[ba(b""), ba(b"")]),
                Other(one=False, five=[ba(b""), ba(b"")]),
                Other(one=True, five=[ba(b"y"), ba(b"")]),
            ]

        self.assertProperties(thing, test_replacement)

    it "complains if setting a value incorrectly":

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [("one", T.BoolInt)]

        class Thing(dictobj.PacketSpec):
            fields = [
                ("one", T.Uint8.enum(E).multiple(3).default(E.ZERO)),
                ("two", T.Int32.multiple(3).default(0)),
                ("three", T.String(32).multiple(3)),
                ("four", T.Bytes(8).multiple(1, kls=Other)),
            ]

        thing = Thing(one=["MEH", E.BLAH], two=[1, 2, 3], three=["on", "two", "thre"])

        def test_thing(thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO]
            assert thing.two == [1, 2, 3]
            assert thing.three == ["on", "two", "thre"]
            assert thing.four == [Other(one=False)]

        test_thing(thing)

        with assertRaises(BadConversion, "Value is not a valid value of the enum"):
            thing.one[-1] = 6
        with assertRaises(BadSpecValue, "Expected an integer"):
            thing.two[0] = "asdf"
        with assertRaises(
            BadSpecValue,
            "BoolInts must be True, False, 0 or 1",
            meta=Meta.empty().at("four").indexed_at(0).at("one"),
        ):
            thing.four[0] = {"one": "asdf"}

        self.assertProperties(thing, test_thing)

    it "can set as bytes":

        class E(enum.Enum):
            ZERO = 0
            MEH = 1
            BLAH = 2

        class Other(dictobj.PacketSpec):
            fields = [("other", T.BoolInt), ("another", T.String(64).default(""))]

        one_fields = [("one", T.Uint8.enum(E).multiple(3).default(E.ZERO))]
        two_fields = [("two", T.Bytes(72).multiple(3, kls=Other))]

        class One(dictobj.PacketSpec):
            fields = one_fields

        class Two(dictobj.PacketSpec):
            fields = two_fields

        class Thing(dictobj.PacketSpec):
            fields = [*one_fields, *two_fields]

        one = One(one=[1, "BLAH", repr(E.ZERO)])
        two = Two(
            two=[
                {"other": False, "another": "wat"},
                {"other": True},
                {"other": False, "another": "hello"},
            ]
        )

        def check(thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO]
            expected = [
                Other.empty_normalise(other=0, another="wat"),
                Other.empty_normalise(other=1, another=""),
                Other.empty_normalise(other=0, another="hello"),
            ]
            assert thing.two == expected

        self.assertProperties(Thing(one=one.one, two=two.two), check)
        self.assertProperties(Thing(one=one.pack(), two=two.pack()), check)

        def check2(thing):
            assert thing.one == [E.MEH, E.BLAH, E.ZERO]
            expected = [
                Other.empty_normalise(other=0, another="wat"),
                Other.empty_normalise(other=0, another="yeap"),
                Other.empty_normalise(other=0, another="hello"),
            ]
            assert thing.two == expected

        thing = Thing(one=one.pack(), two=two.pack())
        thing.two[1] = Other(other=0, another="yeap").pack()
        self.assertProperties(thing, check2)

    it "can edit structs inline":

        class Other(dictobj.PacketSpec):
            fields = [("other", T.BoolInt), ("another", T.String(64).default(""))]

        class Thing(dictobj.PacketSpec):
            fields = [("thing", T.Bytes(72).multiple(3, kls=Other))]

        thing = Thing(
            thing=[
                {"other": False, "another": "wat"},
                {"other": True},
                {"other": False, "another": "hello"},
            ]
        )

        def check(thing):
            expected = [
                Other.empty_normalise(other=0, another="wat"),
                Other.empty_normalise(other=1, another=""),
                Other.empty_normalise(other=0, another="hello"),
            ]
            assert thing.thing == expected

        self.assertProperties(thing, check)

        thing.thing[1].another = "yo"

        def check2(thing):
            expected = [
                Other(other=0, another="wat"),
                Other(other=1, another="yo"),
                Other(other=0, another="hello"),
            ]
            assert list_of_dicts(thing.thing) == list_of_dicts(expected)

        self.assertProperties(thing, check2)

    it "can determine class and number based off other fields":

        class One(dictobj.PacketSpec):
            fields = [("one", T.BoolInt.multiple(4).default(lambda pkt: False))]

        class Two(dictobj.PacketSpec):
            fields = [("two", T.String(32))]

        def choose_kls(pkt):
            if pkt.choice == "one":
                return One
            else:
                return Two

        class Chooser(dictobj.PacketSpec):
            fields = [
                ("choice", T.String(64)),
                ("amount", T.Uint8),
                ("val", T.Bytes(32).multiple(lambda pkt: pkt.amount, kls=choose_kls)),
            ]

        chooser = Chooser(
            choice="one", amount=3, val=[{"one": [True, True, False, True]}, {"one": [False, True]}]
        )

        def check(chooser):
            assert chooser.choice == "one"
            assert chooser.amount == 3
            assert chooser.val == [
                One(one=[True, True, False, True]),
                One(one=[False, True, False, False]),
                One(one=[False, False, False, False]),
            ]

        self.assertProperties(chooser, check)

        chooser = Chooser(choice="two", amount=2, val=[{"two": "wat"}, {"two": "1111"}])

        def check(chooser):
            assert chooser.choice == "two"
            assert chooser.amount == 2
            assert list_of_dicts(chooser.val) == list_of_dicts([Two(two="wat"), Two(two="1111")])

        self.assertProperties(chooser, check)

    it "can determine number based off other fields":

        class Vals(dictobj.PacketSpec):
            fields = [
                ("amount", T.Uint8),
                ("vals", T.Uint8.multiple(lambda pkt: pkt.amount).default(99)),
            ]

        vals = Vals(amount=3, vals=[1, 2])

        def check(vals):
            assert vals.amount == 3
            assert vals.vals == [1, 2, 99]

        self.assertProperties(vals, check)

        vals = Vals(amount=5, vals=[1, 2, 1, 2, 3])

        def check(vals):
            assert vals.amount == 5
            assert vals.vals == [1, 2, 1, 2, 3]

        self.assertProperties(vals, check)
