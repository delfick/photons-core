# coding: spec

from photons_control import test_helpers as chp

from photons_control.transform import Transformer, PowerToggle
from photons_messages import DeviceMessages, LightMessages
from photons_transport.fake import FakeDevice
from photons_control.script import Pipeline
from photons_colour import Parser

from delfick_project.norms import dictobj
import itertools
import asyncio
import random
import pytest

light1 = FakeDevice("d073d5000001", chp.default_responders(color=chp.Color(0, 1, 0.3, 2500)))

light2 = FakeDevice(
    "d073d5000002", chp.default_responders(power=65535, color=chp.Color(100, 1, 0.5, 2500))
)

light3 = FakeDevice(
    "d073d5000003", chp.default_responders(power=65535, color=chp.Color(100, 0, 0.8, 2500))
)


@pytest.fixture(scope="module")
async def runner(memory_devices_runner):
    async with memory_devices_runner([light1, light2, light3]) as runner:
        yield runner


@pytest.fixture(autouse=True)
async def reset_runner(runner):
    await runner.per_test()


def generate_options(color, exclude=None):
    zero_to_one = [v / 10 for v in range(1, 10, 1)]

    options = {
        "hue": list(range(0, 360, 1)),
        "saturation": zero_to_one,
        "brightness": zero_to_one,
        "kelvin": list(range(3500, 9000, 50)),
        "power": ["on", "off"],
    }

    extra = {
        "duration": list(range(0, 10, 1)),
        "res_required": [True, False],
        "effect": ["sine", "triangle", "saw"],
        "cycles": list(range(0, 10, 1)),
    }

    def make_state(keys, extra_keys):
        state = {}
        if color is not None:
            state["color"] = color

        for k in keys:
            state[k] = random.choice(options[k])

        for k in extra_keys:
            state[k] = random.choice(extra[k])

        print(f"Generated state: {state}")
        return state

    keys = [k for k in options if exclude is None or k not in exclude]
    random.shuffle(keys)

    for r in range(len(keys)):
        for i, comb in enumerate(itertools.combinations(keys, r + 1)):
            if i > 0:
                break

            for r in (0, 2):
                if r == 0:
                    yield make_state(comb, [])
                else:
                    for j, comb2 in enumerate(itertools.combinations(extra, r)):
                        if j > 0:
                            break

                        yield make_state(comb, comb2)


describe "PowerToggle":

    async def run_and_compare(self, runner, msg, *, expected):
        await runner.target.script(msg).run_with_all(runner.serials)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

    async it "toggles the power", runner:
        expected = {
            light1: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=1),
            ],
            light2: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
            light3: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=1)],
        }
        await self.run_and_compare(runner, PowerToggle(), expected=expected)

        for device in runner.devices:
            device.received = []

        expected = {
            light1: [DeviceMessages.GetPower(), LightMessages.SetLightPower(level=0, duration=2)],
            light2: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
            light3: [
                DeviceMessages.GetPower(),
                LightMessages.SetLightPower(level=65535, duration=2),
            ],
        }
        await self.run_and_compare(runner, PowerToggle(duration=2), expected=expected)

describe "Transformer":

    async def transform(
        self, runner, state, *, expected, keep_brightness=False, transition_color=False
    ):
        msg = Transformer.using(
            state, keep_brightness=keep_brightness, transition_color=transition_color
        )
        await runner.target.script(msg).run_with_all(runner.serials)

        assert len(runner.devices) > 0

        for device in runner.devices:
            if device not in expected:
                assert False, f"No expectation for {device.serial}"

            device.compare_received(expected[device])

    async it "returns an empty list if no power or color options":
        assert Transformer.using({}) == []

    async it "Uses SetPower if no duration", runner:
        msg = DeviceMessages.SetPower(level=0, res_required=False)
        expected = {device: [msg] for device in runner.devices}
        await self.transform(runner, {"power": "off"}, expected=expected)

        await runner.reset_devices()
        msg = DeviceMessages.SetPower(level=65535, res_required=False)
        expected = {device: [msg] for device in runner.devices}
        await self.transform(runner, {"power": "on"}, expected=expected)

    async it "uses SetLightPower if we have duration", runner:
        msg = LightMessages.SetLightPower(level=0, duration=100, res_required=False)
        expected = {device: [msg] for device in runner.devices}
        await self.transform(runner, {"power": "off", "duration": 100}, expected=expected)

        await runner.reset_devices()
        msg = LightMessages.SetLightPower(level=65535, duration=20, res_required=False)
        expected = {device: [msg] for device in runner.devices}
        await self.transform(runner, {"power": "on", "duration": 20}, expected=expected)

    async it "just uses Parser.color_to_msg", runner:
        for color in (random.choice(["red", "blue", "green", "yellow"]), None):
            for state in generate_options(color, exclude=["power"]):
                want = Parser.color_to_msg(color, overrides=state)
                want.res_required = False

                await runner.reset_devices()
                expected = {device: [want] for device in runner.devices}
                await self.transform(runner, state, expected=expected)

    async it "can ignore brightness", runner:
        want = Parser.color_to_msg("hue:200 saturation:1")
        want.res_required = False

        expected = {device: [want] for device in runner.devices}
        await self.transform(
            runner,
            {"color": "hue:200 saturation:1 brightness:0.3"},
            expected=expected,
            keep_brightness=True,
        )

    async it "sets color with duration", runner:
        state = {"color": "blue", "duration": 10}
        want = Parser.color_to_msg("blue", overrides={"duration": 10})
        expected = {device: [want] for device in runner.devices}
        await self.transform(runner, state, expected=expected, keep_brightness=True)

    async it "sets power off even if light already off", runner:
        state = {"color": "blue", "power": "off", "duration": 10}
        power = LightMessages.SetLightPower(level=0, duration=10)
        set_color = Parser.color_to_msg("blue", overrides={"duration": 10})
        expected = {device: [power, set_color] for device in runner.devices}
        await self.transform(runner, state, expected=expected)

    async it "pipelines turn off and color when both color and power=off", runner:
        for state in generate_options("red"):
            state["power"] = "off"
            transformer = Transformer()
            color_message = transformer.color_message(state, False)
            power_message = transformer.power_message(state)

            assert color_message is not None
            assert power_message is not None

            await runner.reset_devices()
            expected = {device: [power_message, color_message] for device in runner.devices}
            await self.transform(runner, state, expected=expected)

    describe "When power on and need color":

        async it "sets power on if it needs to", runner:
            state = {"color": "blue", "power": "on"}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0}),
                    DeviceMessages.SetPower(level=65535),
                    Parser.color_to_msg(
                        "blue", overrides={"brightness": light1.attrs.color.brightness}
                    ),
                ],
                light2: [LightMessages.GetColor(), Parser.color_to_msg("blue")],
                light3: [LightMessages.GetColor(), Parser.color_to_msg("blue")],
            }
            await self.transform(runner, state, expected=expected)

        async it "sets power on if it needs to with duration", runner:
            state = {"color": "blue brightness:0.3", "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    Parser.color_to_msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light2: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
            }
            await self.transform(runner, state, expected=expected)

        async it "can see brightness in state", runner:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    Parser.color_to_msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light2: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue brightness:0.3", overrides={"duration": 10}),
                ],
            }
            await self.transform(runner, state, expected=expected)

        async it "can ignore brightness in color", runner:
            state = {"color": "blue brightness:0.3", "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    Parser.color_to_msg(
                        "blue",
                        overrides={"brightness": light1.attrs.color.brightness, "duration": 10},
                    ),
                ],
                light2: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"duration": 10}),
                ],
            }
            await self.transform(runner, state, expected=expected, keep_brightness=True)

        async it "can ignore brightness in state", runner:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0}),
                    LightMessages.SetLightPower(level=65535, duration=10),
                    Parser.color_to_msg(
                        "blue",
                        overrides={"brightness": light1.attrs.color.brightness, "duration": 10},
                    ),
                ],
                light2: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"duration": 10}),
                ],
            }
            await self.transform(runner, state, expected=expected, keep_brightness=True)

        async it "can retain previous color when powering on", runner:
            state = {"color": "blue", "brightness": 0.3, "power": "on", "duration": 10}
            msg = Parser.color_to_msg("blue", overrides={"brightness": 0})
            msg.set_hue = 0
            msg.set_saturation = 0
            msg.set_kelvin = 0
            expected = {
                light1: [
                    LightMessages.GetColor(),
                    msg,
                    LightMessages.SetLightPower(level=65535, duration=10),
                    Parser.color_to_msg("blue ", overrides={"brightness": 0.3, "duration": 10},),
                ],
                light2: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
                light3: [
                    LightMessages.GetColor(),
                    Parser.color_to_msg("blue", overrides={"brightness": 0.3, "duration": 10}),
                ],
            }
            await self.transform(runner, state, expected=expected, transition_color=True)
