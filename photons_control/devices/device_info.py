from photons_messages import DeviceMessages, LightMessages
from photons_control.planner import PacketPlan

from delfick_project.norms import dictobj
from datetime import datetime, timedelta
from functools import wraps


def as_dictobj(name, infos):
    if isinstance(infos, list):
        keys = infos[0].keys()
    else:
        keys = infos.keys()

    o = type(name, (dictobj,), {"fields": keys})

    if isinstance(infos, list):
        return [o(**info) for info in infos]
    else:
        return o(**infos)


class by_plan_prop:
    pass


class from_pkt_prop:
    def __init__(self, sender_pkt, receiver_kls):
        self.plan = PacketPlan(sender_pkt, receiver_kls)

    def __call__(self, func):
        @wraps(func)
        def process_pkt(info):
            return func(info["result"])

        return by_plan_prop(result=self.plan)(process_pkt)


class DeviceInfo:
    def __init__(self, serial):
        self.serial = serial
        self.mark_as_seen()

    def mark_as_seen(self):
        self.last_seen = datetime.now()

    @by_plan_prop("state")
    def label(self, info):
        return info["state"]["label"]

    @by_plan_prop("state")
    def power(self, info):
        return info["state"]["power"]

    @from_pkt_prop(DeviceMessages.GetGroup, DeviceMessages.StateGroup)
    def group(self, pkt):
        updated_at = datetime.fromtimestamp(pkt.updated_at // 1e9)
        group = {"label": pkt.label, "identifier": pkt.group, "updated_at": updated_at}
        return as_dictobj("Group", group)

    @from_pkt_prop(DeviceMessages.GetLoation, DeviceMessages.StateLocation)
    def location(self, pkt):
        updated_at = datetime.fromtimestamp(pkt.updated_at // 1e9)
        location = {"label": pkt.label, "identifier": pkt.location, "updated_at": updated_at}
        return as_dictobj("Location", location)

    @by_plan_prop("chain")
    def chain(self, info):
        return as_dictobj("Chain", info["chain"])

    @by_plan_prop("product")
    def product(self, info):
        return as_dictobj("Product", info["product"])

    @from_pkt_prop(DeviceMessages.GetInfo, DeviceMessages.StateInfo)
    def online_since(self, pkt):
        return datetime.now() - timedelta(seconds=pkt.uptime)

    @by_plan_prop("state")
    def color(self, info):
        state = info["state"]
        color = {}
        for k in ("hue", "saturation", "brightness", "kelvin"):
            color[k] = state["state"][k]
        return color

    @by_plan_prop("zones")
    def zones(self, info):
        return info["zones"]

    @from_pkt_prop(LightMessages.GetInfrared, LightMessages.StateInfrared)
    def infrared(self, pkt):
        return pkt.brightness

    @by_plan_prop("firmware_effects")
    def firmware_effect(self, info):
        return as_dictobj("FirmwareEffect", info["firmware_effects"])
