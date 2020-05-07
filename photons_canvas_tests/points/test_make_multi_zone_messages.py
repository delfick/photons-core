# coding: spec

from photons_canvas.points.simple_messages import MultizoneMessagesMaker
from photons_canvas.points.color import Color as CanvasColor

from photons_messages import MultiZoneMessages
from photons_messages.fields import Color
from photons_products import Products

from unittest import mock
import pytest


def old_msg(h, s, b, k, *, dur=1, start, end):
    return MultiZoneMessages.SetColorZones(
        start_index=start,
        end_index=end,
        duration=dur,
        ack_required=True,
        res_required=False,
        target="d073d5001337",
        hue=h,
        saturation=s,
        brightness=b,
        kelvin=k,
    )


def assertMsgs(maker, *msgs):
    made = list(maker.msgs)
    if made != list(msgs):
        if made and made[0] | MultiZoneMessages.SetExtendedColorZones:
            assert len(msgs) == 1

            class C:
                def __init__(s, c):
                    s.payload = c

                def __eq__(s, other):
                    return other.payload == s.payload

            made = [C(c) for c in made[0].colors]
            msgs = [C(c) for c in msgs[0].colors]

        different = False
        for i, (g, w) in enumerate(zip(made, msgs)):
            if g != w:
                different = True
                print(f"Message {i} was not the same")
                print(f"Got  {g.payload}")
                print(f"Want {w.payload}")

        if different:
            assert False, maker.cap


describe "MultizoneMessagesMaker":
    describe "new style messages":

        @pytest.fixture
        def cap(self):
            cap = Products.LCM2_Z.cap(2, 80)
            assert cap.has_extended_multizone
            return cap

        it "can produce no messages", cap:
            assert list(MultizoneMessagesMaker("d073d5001337", cap, []).msgs) == []

        it "can produce an extended multizone message", cap:
            maker = MultizoneMessagesMaker(
                "d073d5001337",
                cap,
                [
                    (200, 1, 1, 3500),
                    {"hue": 200, "saturation": 1, "brightness": 1, "kelvin": 3500},
                    None,
                    Color(200, 1, 0, 7000),
                    CanvasColor(300, 0, 0, 2500),
                    *([(12, 0.5, 0.2, 4000)] * 20),
                    (15, 1, 1, 8000),
                ],
            )

            expected = (
                [Color(200, 1, 1, 3500)] * 2
                + [Color(0, 0, 0, 0)]
                + [Color(200, 1, 0, 7000)]
                + [Color(300, 0, 0, 2500)]
                + [Color(12, 0.5, 0.2, 4000)] * 20
                + [Color(15, 1, 1, 8000)]
            )

            assertMsgs(
                maker,
                MultiZoneMessages.SetExtendedColorZones(
                    duration=1,
                    colors_count=25,
                    colors=expected,
                    zone_index=0,
                    target="d073d5001337",
                    ack_required=True,
                    res_required=False,
                ),
            )

    describe "old style messages":
        it "can produce no messages":
            for cap in (Products.LCM1_Z.cap, Products.LCM2_Z.cap):
                assert cap.has_multizone
                assert not cap.has_extended_multizone
                assert list(MultizoneMessagesMaker("d073d5001337", cap, []).msgs) == []

        it "can work with one colour":
            for cap in (Products.LCM1_Z.cap, Products.LCM2_Z.cap):
                assertMsgs(
                    MultizoneMessagesMaker("d073d5001337", cap, [(100, 1, 1, 3500)]),
                    old_msg(100, 1, 1, 3500, start=0, end=0),
                )

                assertMsgs(
                    MultizoneMessagesMaker("d073d5001337", cap, [(100, 1, 1, 3500)], zone_index=40),
                    old_msg(100, 1, 1, 3500, start=40, end=40),
                )

        it "can work with two colours":
            for cap in (Products.LCM1_Z.cap, Products.LCM2_Z.cap):
                assertMsgs(
                    MultizoneMessagesMaker(
                        "d073d5001337", cap, [(100, 1, 1, 3500), (100, 1, 1, 3500)]
                    ),
                    old_msg(100, 1, 1, 3500, start=0, end=1),
                )

                assertMsgs(
                    MultizoneMessagesMaker(
                        "d073d5001337", cap, [(100, 1, 1, 3500), (100, 1, 1, 3500)], zone_index=50
                    ),
                    old_msg(100, 1, 1, 3500, start=50, end=51),
                )

                assertMsgs(
                    MultizoneMessagesMaker(
                        "d073d5001337", cap, [(100, 1, 1, 3500), (100, 1, 0, 9000)]
                    ),
                    old_msg(100, 1, 1, 3500, start=0, end=0),
                    old_msg(100, 1, 0, 9000, start=1, end=1),
                )

                assertMsgs(
                    MultizoneMessagesMaker(
                        "d073d5001337", cap, [(100, 1, 1, 3500), (100, 1, 0, 9000)], duration=20
                    ),
                    old_msg(100, 1, 1, 3500, start=0, end=0, dur=20),
                    old_msg(100, 1, 0, 9000, start=1, end=1, dur=20),
                )

                assertMsgs(
                    MultizoneMessagesMaker(
                        "d073d5001337", cap, [(100, 1, 1, 3500), (100, 1, 0, 9000)], zone_index=30
                    ),
                    old_msg(100, 1, 1, 3500, start=30, end=30),
                    old_msg(100, 1, 0, 9000, start=31, end=31),
                )

        it "can work with many colours":
            for cap in (Products.LCM1_Z.cap, Products.LCM2_Z.cap):
                maker = MultizoneMessagesMaker(
                    "d073d5001337",
                    cap,
                    [
                        (200, 1, 1, 3500),
                        {"hue": 200, "saturation": 1, "brightness": 1, "kelvin": 3500},
                        None,
                        mock.Mock(
                            name="Color",
                            hue=200,
                            saturation=1,
                            brightness=0,
                            kelvin=7000,
                            spec=["hue", "saturation", "brightness", "kelvin"],
                        ),
                        CanvasColor(300, 0, 0, 2500),
                        *([(12, 0.5, 0.2, 4000)] * 20),
                        (15, 1, 1, 8000),
                    ],
                )

                assertMsgs(
                    maker,
                    old_msg(200, 1, 1, 3500, start=0, end=1),
                    old_msg(0, 0, 0, 0, start=2, end=2),
                    old_msg(200, 1, 0, 7000, start=3, end=3),
                    old_msg(300, 0, 0, 2500, start=4, end=4),
                    old_msg(12, 0.5, 0.2, 4000, start=5, end=24),
                    old_msg(15, 1, 1, 8000, start=25, end=25),
                )
