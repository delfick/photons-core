# coding: spec

from photons_control.planner import Gatherer, make_plans, Plan, NoMessages, Skip
from photons_control.test_helpers import Device, ModuleLevelRunner, Color

from photons_app.errors import PhotonsAppError, RunErrors, TimedOut, BadRunWithResults
from photons_app.test_helpers import AsyncTestCase

from photons_messages import DeviceMessages, LightMessages, MultiZoneMessages

from noseOfYeti.tokeniser.async_support import async_noy_sup_setUp
from contextlib import contextmanager
from unittest import mock
import uuid

light1 = Device("d073d5000001", use_sockets=False
    , power = 0
    , label = "bob"
    , infrared = 100
    , color = Color(100, 0.5, 0.5, 4500)
    , product_id = 55
    , firmware_build = 1548977726000000000
    , firmware_major = 3
    , firmware_minor = 50
    )

light2 = Device("d073d5000002", use_sockets=False
    , power = 65535
    , label = "sam"
    , infrared = 0
    , color = Color(200, 0.3, 1, 9000)
    , product_id = 1
    , firmware_build = 1448861477000000000
    , firmware_major = 2
    , firmware_minor = 2
    )

light3 = Device("d073d5000003", use_sockets=False
    , power = 0
    , label = "strip"
    , product_id = 31
    , firmware_build = 1502237570000000000
    , firmware_major = 1
    , firmware_minor = 22
    )

lights = [light1, light2, light3]
mlr = ModuleLevelRunner(lights, use_sockets=False)

setUp = mlr.setUp
tearDown = mlr.tearDown

describe AsyncTestCase, "Gatherer":
    use_default_loop = True

    async before_each:
        self.maxDiff = None
        self.two_lights = [light1.serial, light2.serial]

    def compare_received(self, by_light):
        for light, msgs in by_light.items():
            assert light in lights
            light.compare_received(msgs, keep_duplicates=True)
            light.reset_received()

    @contextmanager
    def modified_time(self):
        class T:
            def __init__(s):
                s.time = 0

            def __call__(s):
                return s.time

            def forward(s, amount):
                s.time += amount

        t = T()
        with mock.patch("time.time", t):
            yield t

    describe "A plan saying NoMessages":
        @mlr.test
        async it "processes without needing messages", runner:
            called = []

            i1 = mock.Mock(name="i1")
            i2 = mock.Mock(name="i2")
            i = {light1.serial: i1, light2.serial: i2}

            class NoMessagesPlan(Plan):
                messages = NoMessages

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return i[s.serial]

            gatherer = Gatherer(runner.target)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": i1})
                  , light2.serial: (True, {"p": i2})
                  }
                )

            self.assertEqual(called
                , [ ("info", light1.serial)
                  , ("info", light2.serial)
                  ]
                )

        @mlr.test
        async it "does not process other messages", runner:
            called = []

            i1 = mock.Mock(name="i1")
            i2 = mock.Mock(name="i2")
            i = {light1.serial: i1, light2.serial: i2}

            class NoMessagesPlan(Plan):
                messages = NoMessages

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return i[s.serial]

            gatherer = Gatherer(runner.target)
            plans = make_plans("power", p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": i1, "power": {"level": 0, "on": False}})
                  , light2.serial: (True, {"p": i2, "power": {"level": 65535, "on": True}})
                  }
                )

            self.assertEqual(called
                , [ ("info", light1.serial)
                  , ("info", light2.serial)
                  ]
                )

        @mlr.test
        async it "can be determined by logic", runner:
            called = []
            i1 = mock.Mock(name="i1")

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light2.serial:
                            return [DeviceMessages.GetLabel()]
                        else:
                            return NoMessages

                    def process(s, pkt):
                        called.append(("process", s.serial))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        if s.serial == light1.serial:
                            return i1
                        else:
                            return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": i1})
                  , light2.serial: (True, {"p": "sam"})
                  }
                )

            self.assertEqual(called
                , [ ("info", light1.serial)
                  , ("process", light2.serial)
                  , ("info", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: []
                  , light2: [DeviceMessages.GetLabel()]
                  , light3: []
                  }
                )

    describe "A plan saying Skip":
        @mlr.test
        async it "has no processing or info", runner:
            called = []

            class NoMessagesPlan(Plan):
                messages = Skip

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": Skip})
                  , light2.serial: (True, {"p": Skip})
                  }
                )

            self.assertEqual(called, [])

        @mlr.test
        async it "does not process other messages", runner:
            called = []

            class NoMessagesPlan(Plan):
                messages = Skip

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append("process")

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans("power", p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": Skip, "power": {"level": 0, "on": False}})
                  , light2.serial: (True, {"p": Skip, "power": {"level": 65535, "on": True}})
                  }
                )

            self.assertEqual(called, [])

        @mlr.test
        async it "can be determined by logic", runner:
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light2.serial:
                            return [DeviceMessages.GetLabel()]
                        else:
                            return Skip

                    def process(s, pkt):
                        called.append(("process", s.serial))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(p=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"p": Skip})
                  , light2.serial: (True, {"p": "sam"})
                  }
                )

            self.assertEqual(called
                , [ ("process", light2.serial)
                  , ("info", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: []
                  , light2: [DeviceMessages.GetLabel()]
                  , light3: []
                  }
                )

    describe "A plan with no messages":
        @mlr.test
        async it "it gets all other messages", runner:
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        self.assertEqual(pkt.serial, s.serial)
                        called.append((pkt.serial, pkt.payload.as_dict()))

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans("label", "power", other=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "power": {"level": 0, "on": False}, "other": True})
                  , light2.serial: (True, {"label": "sam", "power": {"level": 65535, "on": True}, "other": True})
                  }
                )

            self.assertEqual(called
                , [ (light1.serial, {"label": "bob"})
                  , (light1.serial, {"level": 0})
                  , (light2.serial, {"label": "sam"})
                  , (light2.serial, {"level": 65535})
                  , ("info", light1.serial)
                  , ("info", light2.serial)
                  ]
                )

        @mlr.test
        async it "still finishes if no messages processed but finished_after_no_more_messages", runner:
            called = []

            class NoMessagesPlan(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        self.assertEqual(pkt.serial, s.serial)
                        called.append((pkt.serial, pkt.payload.as_dict()))

                    async def info(s):
                        called.append(("info", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans(other=NoMessagesPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"other": True})
                  , light2.serial: (True, {"other": True})
                  }
                )

            self.assertEqual(called
                , [ ("info", light1.serial)
                  , ("info", light2.serial)
                  ]
                )

    describe "a plan that never finishes":
        @mlr.test
        async it "it doesn't get recorded", runner:
            called = []

            class NeverFinishedPlan(Plan):
                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("process", pkt.serial))

                    async def info(s):
                        called.append(("info", s.serial))

            gatherer = Gatherer(runner.target)
            plans = make_plans("label", "power", other=NeverFinishedPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (False, {"label": "bob", "power": {"level": 0, "on": False}})
                  , light2.serial: (False, {"label": "sam", "power": {"level": 65535, "on": True}})
                  }
                )

            self.assertEqual(called
                , [ ("process", light1.serial)
                  , ("process", light1.serial)
                  , ("process", light2.serial)
                  , ("process", light2.serial)
                  ]
                )

    describe "A plan with messages":
        @mlr.test
        async it "messages are processed until we say plan is done", runner:
            called = []

            class SimplePlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append((pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info", s.serial))
                        return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(simple=SimplePlan())

            found = []
            async for serial, label, info in gatherer.gather(plans, self.two_lights):
                found.append((serial, label, info))

            self.assertEqual(found
                , [ (light1.serial, "simple", "bob")
                  , (light2.serial, "simple", "sam")
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type

            self.assertEqual(called
                , [ (light1.serial, label_type)
                  , ("info", light1.serial)
                  , (light2.serial, label_type)
                  , ("info", light2.serial)
                  ]
                )

        @mlr.test
        async it "raises errors after yielding everything", runner:
            called = []

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            class PowerPlan(Plan):
                messages = [DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("power", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        return s.level

            class Looker(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        called.append(("looker", pkt.serial, pkt.pkt_type))

                    async def info(s):
                        called.append(("info.looker", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans(power=PowerPlan(), label=LabelPlan(), looker=Looker())

            found = []
            error = TimedOut("Waiting for reply to a packet", serial=light1.serial)
            with self.fuzzyAssertRaisesError(RunErrors, _errors=[error]):
                with light1.no_reply_to(DeviceMessages.GetLabel):
                    async for serial, label, info in gatherer.gather(plans, self.two_lights, message_timeout=0.05):
                        found.append((serial, label, info))

            self.assertEqual(found
                , [ (light1.serial, "power", 0)
                  , (light2.serial, "label", "sam")
                  , (light2.serial, "power", 65535)
                  , (light2.serial, "looker", True)
                  , (light1.serial, "looker", True)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  , ("looker", light1.serial, power_type)
                  , ("power", light1.serial, power_type)
                  , ("info.power", light1.serial)

                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  , ("looker", light2.serial, label_type)
                  , ("power", light2.serial, label_type)
                  , ("looker", light2.serial, power_type)
                  , ("power", light2.serial, power_type)
                  , ("info.power", light2.serial)
                  , ("info.looker", light2.serial)
                  , ("info.looker", light1.serial)
                  ]
                )

            found.clear()
            called.clear()
            with self.fuzzyAssertRaisesError(RunErrors, _errors=[error]):
                with light1.no_reply_to(DeviceMessages.GetLabel):
                    async for serial, completed, info in gatherer.gather_per_serial(plans, self.two_lights, message_timeout=0.05):
                        found.append((serial, completed, info))

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  ]
                )

            self.assertEqual(found
                , [ (light2.serial, True, {"looker": True,"label": "sam", "power": 65535})
                  , (light1.serial, False, {"looker": True, "power": 0})
                  ]
                )

            called.clear()
            try:
                with light1.no_reply_to(DeviceMessages.GetLabel):
                    await gatherer.gather_all(plans, self.two_lights, message_timeout=0.05)
            except BadRunWithResults as e:
                self.assertEqual(e.errors, [error])
                found = e.kwargs["results"]

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  ]
                )

            self.assertEqual(found
                , { light2.serial: (True, {"looker": True, "label": "sam", "power": 65535})
                  , light1.serial: (False, {"looker": True, "power": 0})
                  }
                )

        @mlr.test
        async it "doesn't raise errors if we have an error catcher", runner:
            called = []

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            class PowerPlan(Plan):
                messages = [DeviceMessages.GetPower()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("power", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        return s.level

            class Looker(Plan):
                class Instance(Plan.Instance):
                    finished_after_no_more_messages = True

                    def process(s, pkt):
                        called.append(("looker", pkt.serial, pkt.pkt_type))

                    async def info(s):
                        called.append(("info.looker", s.serial))
                        return True

            gatherer = Gatherer(runner.target)
            plans = make_plans(power=PowerPlan(), label=LabelPlan(), looker=Looker())
            error_catcher = []
            kwargs = {"message_timeout": 0.05, "error_catcher": error_catcher}

            found = []
            error = TimedOut("Waiting for reply to a packet", serial=light1.serial)

            with light1.no_reply_to(DeviceMessages.GetLabel):
                async for serial, label, info in gatherer.gather(plans, self.two_lights, **kwargs):
                    found.append((serial, label, info))

            self.assertEqual(error_catcher, [error])
            error_catcher.clear()

            self.assertEqual(found
                , [ (light1.serial, "power", 0)
                  , (light2.serial, "label", "sam")
                  , (light2.serial, "power", 65535)
                  , (light2.serial, "looker", True)
                  , (light1.serial, "looker", True)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  , ("looker", light1.serial, power_type)
                  , ("power", light1.serial, power_type)
                  , ("info.power", light1.serial)

                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  , ("looker", light2.serial, label_type)
                  , ("power", light2.serial, label_type)
                  , ("looker", light2.serial, power_type)
                  , ("power", light2.serial, power_type)
                  , ("info.power", light2.serial)
                  , ("info.looker", light2.serial)
                  , ("info.looker", light1.serial)
                  ]
                )

            found.clear()
            called.clear()
            with light1.no_reply_to(DeviceMessages.GetLabel):
                async for serial, completed, info in gatherer.gather_per_serial(plans, self.two_lights, **kwargs):
                    found.append((serial, completed, info))

            self.assertEqual(error_catcher, [error])
            error_catcher.clear()

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  ]
                )

            self.assertEqual(found
                , [ (light2.serial, True, {"looker": True, "label": "sam", "power": 65535})
                  , (light1.serial, False, {"looker": True, "power": 0})
                  ]
                )

            called.clear()
            with light1.no_reply_to(DeviceMessages.GetLabel):
                found = dict(await gatherer.gather_all(plans, self.two_lights, **kwargs))

            self.assertEqual(error_catcher, [error])
            error_catcher.clear()

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, power_type)
                  ]
                )

            self.assertEqual(found
                , { light2.serial: (True, {"looker": True, "label": "sam", "power": 65535})
                  , light1.serial: (False, {"looker": True, "power": 0})
                  }
                )

    describe "refreshing":
        @mlr.test
        async it "it can refresh always", runner:
            called = []

            class LabelPlan(Plan):
                default_refresh = True
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, light1.serial))
            self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})

            label_type = DeviceMessages.StateLabel.Payload.message_type

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            called.clear()

            # Get it again, default refresh means it will be cached
            got = dict(await gatherer.gather_all(plans, light1.serial))
            self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: []
                  , light3: []
                  }
                )

            called.clear()

            # We can override refresh
            plans = make_plans(label=LabelPlan(refresh=False))
            got = dict(await gatherer.gather_all(plans, light1.serial))
            self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})

            self.assertEqual(called, [])
            self.compare_received(
                  { light1: []
                  , light2: []
                  , light3: []
                  }
                )

        @mlr.test
        async it "it can refresh on time", runner:
            with self.modified_time() as t:
                called = []
    
                class LabelPlan(Plan):
                    default_refresh = 1
                    messages = [DeviceMessages.GetLabel()]
    
                    class Instance(Plan.Instance):
                        def process(s, pkt):
                            called.append(("label", pkt.serial, pkt.pkt_type))
    
                            if pkt | DeviceMessages.StateLabel:
                                s.label = pkt.label
                                return True
    
                        async def info(s):
                            called.append(("info.label", s.serial))
                            return s.label
    
                gatherer = Gatherer(runner.target)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, light1.serial))
                self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})
    
                label_type = DeviceMessages.StateLabel.Payload.message_type
    
                self.assertEqual(called
                    , [ ("label", light1.serial, label_type)
                      , ("info.label", light1.serial)
                      ]
                    )
    
                self.compare_received(
                      { light1: [DeviceMessages.GetLabel()]
                      , light2: []
                      , light3: []
                      }
                    )
    
                called.clear()
    
                # Get it again, our refresh means it will be cached
                t.forward(0.6)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, light1.serial))
                self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})
    
                self.assertEqual(called, [])
                self.compare_received(
                      { light1: []
                      , light2: []
                      , light3: []
                      }
                    )
    
                # After a second, we get refreshed
                t.forward(0.5)
                got = dict(await gatherer.gather_all(plans, light1.serial))
                self.assertEqual(got, {light1.serial: (True, {"label": "bob"})})
    
                self.assertEqual(called
                    , [ ("label", light1.serial, label_type)
                      , ("info.label", light1.serial)
                      ]
                    )
    
                self.compare_received(
                      { light1: [DeviceMessages.GetLabel()]
                      , light2: []
                      , light3: []
                      }
                    )
    
                called.clear()

        @mlr.test
        async it "it can have different refresh based on logic in the instance", runner:
            with self.modified_time() as t:
                called = []
    
                class LabelPlan(Plan):
                    messages = [DeviceMessages.GetLabel()]
    
                    class Instance(Plan.Instance):
                        @property
                        def refresh(s):
                            if s.serial == light1.serial:
                                return 1
                            elif s.serial == light2.serial:
                                return 2
                            else:
                                assert False, "unknown serial"

                        def process(s, pkt):
                            called.append(("label", pkt.serial, pkt.pkt_type))
    
                            if pkt | DeviceMessages.StateLabel:
                                s.label = pkt.label
                                return True
    
                        async def info(s):
                            called.append(("info.label", s.serial))
                            return s.label
    
                gatherer = Gatherer(runner.target)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, self.two_lights))
                self.assertEqual(got
                    , { light1.serial: (True, {"label": "bob"})
                      , light2.serial: (True, {"label": "sam"})
                      }
                    )
    
                label_type = DeviceMessages.StateLabel.Payload.message_type
    
                self.assertEqual(called
                    , [ ("label", light1.serial, label_type)
                      , ("info.label", light1.serial)
                      , ("label", light2.serial, label_type)
                      , ("info.label", light2.serial)
                      ]
                    )
    
                self.compare_received(
                      { light1: [DeviceMessages.GetLabel()]
                      , light2: [DeviceMessages.GetLabel()]
                      , light3: []
                      }
                    )
    
                called.clear()
    
                # Get it again, our refresh means it will be cached
                t.forward(0.6)
                plans = make_plans(label=LabelPlan())
                got = dict(await gatherer.gather_all(plans, self.two_lights))
                self.assertEqual(got
                    , { light1.serial: (True, {"label": "bob"})
                      , light2.serial: (True, {"label": "sam"})
                      }
                    )
    
                self.assertEqual(called, [])
                self.compare_received(
                      { light1: []
                      , light2: []
                      , light3: []
                      }
                    )
    
                # After a second, we get light1 refreshed
                t.forward(0.5)
                got = dict(await gatherer.gather_all(plans, self.two_lights))
                self.assertEqual(got
                    , { light1.serial: (True, {"label": "bob"})
                      , light2.serial: (True, {"label": "sam"})
                      }
                    )
    
                self.assertEqual(called
                    , [ ("label", light1.serial, label_type)
                      , ("info.label", light1.serial)
                      ]
                    )
    
                self.compare_received(
                      { light1: [DeviceMessages.GetLabel()]
                      , light2: []
                      , light3: []
                      }
                    )
    
                called.clear()

                # After two seconds, we get both refreshed
                t.forward(1)
                got = dict(await gatherer.gather_all(plans, self.two_lights))
                self.assertEqual(got
                    , { light1.serial: (True, {"label": "bob"})
                      , light2.serial: (True, {"label": "sam"})
                      }
                    )
    
                self.assertEqual(called
                    , [ ("label", light1.serial, label_type)
                      , ("info.label", light1.serial)
                      , ("label", light2.serial, label_type)
                      , ("info.label", light2.serial)
                      ]
                    )
    
                self.compare_received(
                      { light1: [DeviceMessages.GetLabel()]
                      , light2: [DeviceMessages.GetLabel()]
                      , light3: []
                      }
                    )
    
                called.clear()

        @mlr.test
        async it "cannot steal messages from completed plans if we refresh messages those other plans use", runner:
            called = []

            class ReverseLabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("reverse", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.reverse", s.serial))
                        return ''.join(reversed(s.label))

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = True

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(rev=ReverseLabelPlan(), label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "rev": "bob"})
                  , light2.serial: (True, {"label": "sam", "rev": "mas"})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  , ("reverse", light1.serial, label_type)
                  , ("info.reverse", light1.serial)
                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  , ("reverse", light2.serial, label_type)
                  , ("info.reverse", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel()]
                  , light3: []
                  }
                )

            called.clear()

            # Get it again, our refresh means we process LabelPlan again,
            # but using results from ReverseLabelPlan
            got = dict(await gatherer.gather_all(plans, self.two_lights))
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "rev": "bob"})
                  , light2.serial: (True, {"label": "sam", "rev": "mas"})
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel()]
                  , light3: []
                  }
                )

        @mlr.test
        async it "has no cached completed data if instance has no key", runner:
            called = []

            class ReverseLabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("reverse", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.reverse", s.serial))
                        return ''.join(reversed(s.label))

            class LabelPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                default_refresh = False

                class Instance(Plan.Instance):
                    def key(s):
                        return None

                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.label", s.serial))
                        return s.label

            gatherer = Gatherer(runner.target)
            plans = make_plans(rev=ReverseLabelPlan(), label=LabelPlan())
            got = dict(await gatherer.gather_all(plans, self.two_lights))
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "rev": "bob"})
                  , light2.serial: (True, {"label": "sam", "rev": "mas"})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  , ("reverse", light1.serial, label_type)
                  , ("info.reverse", light1.serial)
                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  , ("reverse", light2.serial, label_type)
                  , ("info.reverse", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel()]
                  , light3: []
                  }
                )

            called.clear()

            # Get it again, our refresh means we process LabelPlan again,
            # but using results from ReverseLabelPlan
            got = dict(await gatherer.gather_all(plans, self.two_lights))
            self.assertEqual(got
                , { light1.serial: (True, {"label": "bob", "rev": "bob"})
                  , light2.serial: (True, {"label": "sam", "rev": "mas"})
                  }
                )

            self.assertEqual(called
                , [ ("label", light1.serial, label_type)
                  , ("info.label", light1.serial)
                  , ("label", light2.serial, label_type)
                  , ("info.label", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: []
                  , light2: []
                  , light3: []
                  }
                )

    describe "dependencies":
        @mlr.test
        async it "it can get dependencies", runner:
            called = []

            class PowerPlan(Plan):
                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.serial == light3.serial:
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("power", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.power", s.serial))
                        return s.level

            class InfoPlan(Plan):
                messages = [DeviceMessages.GetLabel()]
                dependant_info = {"p": PowerPlan()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["p"] == 0:
                            return [LightMessages.GetInfrared()]
                        else:
                            return [DeviceMessages.GetLabel()]

                    def process(s, pkt):
                        called.append(("label", pkt.serial, pkt.pkt_type))

                        if pkt | DeviceMessages.StateLabel:
                            s.i = pkt.label
                            return True
                        elif pkt | LightMessages.StateInfrared:
                            s.i = pkt.brightness
                            return True

                    async def info(s):
                        called.append(("info.info", s.serial))
                        return {"power": s.deps["p"], "info": s.i}

            gatherer = Gatherer(runner.target)
            plans = make_plans(info=InfoPlan())
            got = dict(await gatherer.gather_all(plans, runner.serials))

            self.assertEqual(got
                , { light1.serial: (True, {"info": {"power": 0, "info": 100}})
                  , light2.serial: (True, {"info": {"power": 65535, "info": "sam"}})
                  , light3.serial: (True, {"info": {"power": Skip, "info": "strip"}})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type
            infrared_type = LightMessages.StateInfrared.Payload.message_type

            self.assertEqual(called
                , [ ("power", light1.serial, power_type)
                  , ("info.power", light1.serial)
                  , ("power", light2.serial, power_type)
                  , ("info.power", light2.serial)

                  , ("label", light3.serial, label_type)
                  , ("info.info", light3.serial)
                  , ("label", light1.serial, power_type)
                  , ("label", light2.serial, power_type)
                  , ("label", light1.serial, infrared_type)
                  , ("info.info", light1.serial)
                  , ("label", light2.serial, label_type)
                  , ("info.info", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetPower(), LightMessages.GetInfrared()]
                  , light2: [DeviceMessages.GetPower(), DeviceMessages.GetLabel()]
                  , light3: [DeviceMessages.GetLabel()]
                  }
                )

        @mlr.test
        async it "it can get dependencies of dependencies and messages can be shared", runner:
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                messages = [DeviceMessages.GetLabel()]
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "rev": "".join(reversed(s.label))}

            class Plan3(Plan):
                messages = [DeviceMessages.GetPower()]
                dependant_info = {"p": Plan2()}

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan3", pkt.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan3", s.serial))
                        return (s.level, s.deps["p"])

            gatherer = Gatherer(runner.target)
            plans = make_plans(plan3=Plan3())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"plan3": (0, {"label": "bob", "rev": "bob"})})
                  , light2.serial: (True, {"plan3": (65535, {"label": "sam", "rev": "mas"})})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("plan1", light1.serial, label_type)
                  , ("info.plan1", light1.serial)
                  , ("plan1", light2.serial, label_type)
                  , ("info.plan1", light2.serial)

                  , ("plan2", light1.serial, label_type)
                  , ("info.plan2", light1.serial)
                  , ("plan2", light2.serial, label_type)
                  , ("info.plan2", light2.serial)

                  , ("plan3", light1.serial, label_type)
                  , ("plan3", light2.serial, label_type)
                  , ("plan3", light1.serial, power_type)
                  , ("info.plan3", light1.serial)
                  , ("plan3", light2.serial, power_type)
                  , ("info.plan3", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )

        @mlr.test
        async it "it can skip based on dependency", runner:
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(runner.target)
            plans = make_plans(plan2=Plan2())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"plan2": Skip})
                  , light2.serial: (True, {"plan2": {"label": "sam", "power": 65535}})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("plan1", light1.serial, label_type)
                  , ("info.plan1", light1.serial)
                  , ("plan1", light2.serial, label_type)
                  , ("info.plan1", light2.serial)

                  , ("plan2", light2.serial, label_type)
                  , ("plan2", light2.serial, power_type)
                  , ("info.plan2", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )
            
        @mlr.test
        async it "can get results from deps as well", runner:
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(runner.target)
            plans = make_plans(plan1=Plan1(), plan2=Plan2())
            got = dict(await gatherer.gather_all(plans, self.two_lights))

            self.assertEqual(got
                , { light1.serial: (True, {"plan1": "bob", "plan2": Skip})
                  , light2.serial: (True, {"plan1": "sam", "plan2": {"label": "sam", "power": 65535}})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("plan1", light1.serial, label_type)
                  , ("info.plan1", light1.serial)
                  , ("plan1", light2.serial, label_type)
                  , ("info.plan1", light2.serial)

                  , ("plan2", light2.serial, label_type)
                  , ("plan2", light2.serial, power_type)
                  , ("info.plan2", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: []
                  }
                )

        @mlr.test
        async it "chain is broken when dep can't get results", runner:
            called = []

            class Plan1(Plan):
                messages = [DeviceMessages.GetLabel()]

                class Instance(Plan.Instance):
                    def process(s, pkt):
                        called.append(("plan1", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StateLabel:
                            s.label = pkt.label
                            return True

                    async def info(s):
                        called.append(("info.plan1", s.serial))
                        return s.label

            class Plan2(Plan):
                dependant_info = {"l": Plan1()}

                class Instance(Plan.Instance):
                    @property
                    def messages(s):
                        if s.deps["l"] == "bob":
                            return Skip
                        else:
                            return [DeviceMessages.GetPower()]

                    def process(s, pkt):
                        called.append(("plan2", s.serial, pkt.pkt_type))
                        if pkt | DeviceMessages.StatePower:
                            s.level = pkt.level
                            return True

                    async def info(s):
                        called.append(("info.plan2", s.serial))
                        return {"label": s.deps["l"], "power": s.level}

            gatherer = Gatherer(runner.target)
            plans = make_plans("presence", plan2=Plan2())
            errors = []
            with light3.no_reply_to(DeviceMessages.GetLabel):
                got = dict(await gatherer.gather_all(plans, runner.serials, error_catcher=errors, message_timeout=0.05))
            self.assertEqual(len(errors), 1)

            self.assertEqual(got
                , { light1.serial: (True, {"presence": True, "plan2": Skip})
                  , light2.serial: (True, {"presence": True, "plan2": {"label": "sam", "power": 65535}})
                  , light3.serial: (False, {"presence": True})
                  }
                )

            label_type = DeviceMessages.StateLabel.Payload.message_type
            power_type = DeviceMessages.StatePower.Payload.message_type

            self.assertEqual(called
                , [ ("plan1", light1.serial, label_type)
                  , ("info.plan1", light1.serial)
                  , ("plan1", light2.serial, label_type)
                  , ("info.plan1", light2.serial)

                  , ("plan2", light2.serial, label_type)
                  , ("plan2", light2.serial, power_type)
                  , ("info.plan2", light2.serial)
                  ]
                )

            self.compare_received(
                  { light1: [DeviceMessages.GetLabel()]
                  , light2: [DeviceMessages.GetLabel(), DeviceMessages.GetPower()]
                  , light3: [DeviceMessages.GetLabel()]
                  }
                )
