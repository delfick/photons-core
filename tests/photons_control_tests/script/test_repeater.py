# coding: spec

from photons_control.script import Repeater, Pipeline
from photons_control import test_helpers as chp

from photons_app.special import FoundSerials

from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice

from collections import defaultdict
import asyncio
import pytest

light1 = FakeDevice("d073d5000001", chp.default_responders())
light2 = FakeDevice("d073d5000002", chp.default_responders())
light3 = FakeDevice("d073d5000003", chp.default_responders())


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2, light3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


def loop_time():
    return asyncio.get_event_loop().time()


describe "Repeater":

    async it "repeats messages", runner:
        for use_pipeline in (True, False):
            pipeline = [
                DeviceMessages.SetPower(level=0),
                LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
            ]

            if use_pipeline:
                pipeline = Pipeline(*pipeline)

            msg = Repeater(pipeline, min_loop_time=0)

            def no_errors(err):
                assert False, f"Got an error: {err}"

            got = defaultdict(list)
            async for pkt in runner.sender(msg, FoundSerials(), error_catcher=no_errors):
                got[pkt.serial].append(pkt)
                if all(len(pkts) >= 6 for pkts in got.values()):
                    break

            assert all(serial in got for serial in runner.serials), got

            for pkts in got.values():
                got_power = False
                got_light = False
                if len(pkts) < 6:
                    assert False, ("Expected at least 6 replies", pkts, serial)

                while pkts:
                    nxt = pkts.pop()
                    if nxt | DeviceMessages.StatePower:
                        if got_power:
                            assert False, "Expected a LightState"
                        got_power = True
                    elif nxt | LightMessages.LightState:
                        if got_light:
                            assert False, "Expected a StatePower"
                        got_light = True
                    else:
                        assert False, f"Got an unexpected packet: {nxt}"

                    if got_power and got_light:
                        got_power = False
                        got_light = False

    @pytest.mark.async_timeout(3)
    async it "can have a min loop time", runner:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        msg = Repeater(msgs, min_loop_time=0.5)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        got = defaultdict(list)
        async for pkt in runner.sender(msg, runner.serials, error_catcher=no_errors):
            got[pkt.serial].append((pkt, loop_time()))
            if all(len(pkts) >= 6 for pkts in got.values()):
                break

        assert all(serial in got for serial in runner.serials), got

        for pkts in got.values():
            if len(pkts) < 6:
                assert False, ("Expected at least 6 replies", pkts, serial)

            first = pkts.pop(0)[1]
            current = pkts.pop(0)[1]

            while pkts:
                assert current - first < 0.1

                nxt = pkts.pop(0)[1]
                assert nxt - current > 0.3
                current = nxt

                if pkts:
                    first = pkts.pop(0)[1]

    async it "can have a on_done_loop", runner:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)

        msg = Repeater(msgs, on_done_loop=on_done, min_loop_time=0)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        got = defaultdict(list)
        async for pkt in runner.sender(msg, runner.serials, error_catcher=no_errors):
            got[pkt.serial].append((pkt, loop_time()))
            if all(len(pkts) >= 7 for pkts in got.values()):
                break

        assert all(serial in got for serial in runner.serials), got
        assert len(done) == 3

    async it "can be stopped by a on_done_loop", runner:
        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)
            if len(done) == 3:
                raise Repeater.Stop

        msg = Repeater(msgs, on_done_loop=on_done, min_loop_time=0)

        def no_errors(err):
            assert False, f"Got an error: {err}"

        got = defaultdict(list)
        async for pkt in runner.sender(msg, runner.serials, error_catcher=no_errors):
            got[pkt.serial].append((pkt, loop_time()))

        assert all(serial in got for serial in runner.serials), got
        assert all(len(pkts) == 6 for pkts in got.values()), [
            (serial, len(pkts)) for serial, pkts in got.items()
        ]
        assert len(done) == 3

    async it "is not stopped by errors", runner:

        async def waiter(pkt, source):
            if pkt | DeviceMessages.SetPower:
                return False

        light1.set_intercept_got_message(waiter)
        light2.set_intercept_got_message(waiter)
        light3.set_intercept_got_message(waiter)

        msgs = [
            DeviceMessages.SetPower(level=0),
            LightMessages.SetColor(hue=0, saturation=0, brightness=1, kelvin=4500),
        ]

        done = []

        async def on_done():
            done.append(True)
            if len(done) == 2:
                raise Repeater.Stop

        msg = Repeater(msgs, on_done_loop=on_done, min_loop_time=0)

        errors = []

        def got_error(err):
            errors.append(err)

        got = defaultdict(list)
        async for pkt in runner.sender(
            msg, runner.serials, error_catcher=got_error, message_timeout=0.1
        ):
            got[pkt.serial].append(pkt)

        assert all(serial in got for serial in runner.serials), got
        assert all(len(pkts) == 2 for pkts in got.values()), [
            (serial, len(pkts)) for serial, pkts in got.items()
        ]
        assert all(
            all(pkt | LightMessages.LightState for pkt in pkts) for pkts in got.values()
        ), got
        assert len(done) == 2
