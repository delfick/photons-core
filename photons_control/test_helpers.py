from photons_app.errors import PhotonsAppError
from photons_app import helpers as hp

from photons_messages import (
    LightMessages,
    DeviceMessages,
    MultiZoneMessages,
    TileMessages,
    MultiZoneEffectType,
    TileEffectType,
    protocol_register,
    fields,
)
from photons_transport.targets import MemoryTarget
from photons_products import Products, Family
from photons_protocol.types import enum_spec
from photons_transport.fake import Responder

from delfick_project.norms import dictobj, sb, Meta
import logging
import asyncio

log = logging.getLogger("photons_control.test_helpers")


def Color(hue, saturation, brightness, kelvin):
    return fields.Color(hue=hue, saturation=saturation, brightness=brightness, kelvin=kelvin)


class TileChild(dictobj.Spec):
    accel_meas_x = dictobj.Field(sb.integer_spec, default=0)
    accel_meas_y = dictobj.Field(sb.integer_spec, default=0)
    accel_meas_z = dictobj.Field(sb.integer_spec, default=0)
    user_x = dictobj.Field(sb.integer_spec, default=0)
    user_y = dictobj.Field(sb.integer_spec, default=0)
    width = dictobj.Field(sb.integer_spec, default=8)
    height = dictobj.Field(sb.integer_spec, default=8)
    device_version_vendor = dictobj.Field(sb.integer_spec, default=1)
    device_version_product = dictobj.Field(sb.integer_spec, default=55)
    device_version_version = dictobj.Field(sb.integer_spec, default=0)
    firmware_version_minor = dictobj.Field(sb.integer_spec, default=50)
    firmware_version_major = dictobj.Field(sb.integer_spec, default=3)
    firmware_build = dictobj.Field(sb.integer_spec, default=0)


class LightStateResponder(Responder):
    _fields = [("color", lambda: Color(0, 0, 1, 3500)), ("power", lambda: 0), ("label", lambda: "")]

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetLabel:
            yield self.make_label_response(device)
        elif pkt | DeviceMessages.SetLabel:
            device.attrs.label = pkt.label
            yield self.make_label_response(device)

        elif pkt | DeviceMessages.GetPower:
            yield self.make_power_response(device)
        elif pkt | DeviceMessages.SetPower:
            res = self.make_power_response(device)
            device.attrs.power = pkt.level
            yield res
        elif pkt | LightMessages.SetLightPower:
            res = self.make_light_power_response(device)
            device.attrs.power = pkt.level
            yield res

        elif pkt | LightMessages.GetColor:
            yield self.make_light_response(device)
        elif pkt | LightMessages.SetColor or pkt | LightMessages.SetWaveform:
            res = self.make_light_response(device)
            device.attrs.color = Color(pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin)
            yield res
        elif pkt | LightMessages.SetWaveformOptional:
            res = self.make_light_response(device)

            color = Color(**device.attrs.color.as_dict())
            for p in ("hue", "saturation", "brightness", "kelvin"):
                if getattr(pkt, f"set_{p}"):
                    color[p] = pkt[p]

            device.attrs.color = color
            yield res

    def make_label_response(self, device):
        return DeviceMessages.StateLabel(label=device.attrs.label)

    def make_power_response(self, device):
        return DeviceMessages.StatePower(level=device.attrs.power)

    def make_light_power_response(self, device):
        return LightMessages.StateLightPower(level=device.attrs.power)

    def make_light_response(self, device):
        return LightMessages.LightState.empty_normalise(
            label=device.attrs.label, power=device.attrs.power, **device.attrs.color.as_dict()
        )


class InfraredResponder(Responder):
    _fields = [("infrared", lambda: 0)]

    def has_infrared(self, device):
        cap = ProductResponder.capability(device)
        return cap.has_ir or cap.product.family is Family.LCM3

    async def reset(self, device, *, zero=False):
        if self.has_infrared(device):
            await super().reset(device, zero=zero)

    async def respond(self, device, pkt, source):
        if not self.has_infrared(device):
            return

        if pkt | LightMessages.GetInfrared:
            yield self.make_response(device)
        elif pkt | LightMessages.SetInfrared:
            res = self.make_response(device)
            device.attrs.infrared = pkt.brightness
            yield res

    def make_response(self, device):
        return LightMessages.StateInfrared(brightness=device.attrs.infrared)


class MatrixResponder(Responder):
    _fields = [
        ("chain", lambda: []),
        ("palette", lambda: []),
        ("chain_length", lambda: 5),
        ("matrix_width", lambda: 8),
        ("matrix_height", lambda: 8),
        ("matrix_effect", lambda: TileEffectType.OFF),
        ("palette_count", lambda: 0),
    ]

    async def start(self, device):
        if "chain" not in device.attrs:
            return

        cap = ProductResponder.capability(device)
        if not device.attrs.chain:
            for _ in range(device.attrs.chain_length):
                child = TileChild.FieldSpec().empty_normalise(
                    firmware_version_major=cap.firmware_major,
                    firmware_version_minor=cap.firmware_minor,
                    device_version_vendor=cap.product.vendor.vid,
                    device_version_product=cap.product.pid,
                    width=device.attrs.matrix_width,
                    height=device.attrs.matrix_height,
                )
                colors = [Color(0, 0, 0, 3500) for _ in range(64)]
                device.attrs.chain.append((child, colors))

    def has_matrix(self, device):
        return ProductResponder.capability(device).has_matrix

    async def reset(self, device, *, zero=False):
        if self.has_matrix(device):
            await super().reset(device, zero=zero)

    async def respond(self, device, pkt, source):
        if not self.has_matrix(device):
            return

        if pkt | TileMessages.GetTileEffect:
            yield self.make_state_tile_effect(device)

        elif pkt | TileMessages.SetTileEffect:
            res = self.make_state_tile_effect(device, instanceid=pkt.instanceid)
            device.attrs.palette = pkt.palette
            device.attrs.palette_count = pkt.palette_count
            device.attrs.matrix_effect = pkt.type
            yield res

        elif pkt | TileMessages.GetDeviceChain:
            yield self.make_device_chain(device)

        elif pkt | TileMessages.Get64:
            for msg in self.make_state_64s(device, pkt):
                yield msg

        elif pkt | TileMessages.Set64:
            replies = list(self.make_state_64s(device, pkt))

            for i in range(pkt.tile_index, pkt.length):
                if i < len(device.attrs.chain):
                    chain, colors = device.attrs.chain[i]
                    colors.clear()
                    colors.extend(pkt.colors)

            for msg in replies:
                yield msg

    def make_state_tile_effect(self, device, instanceid=sb.NotSpecified):
        return TileMessages.StateTileEffect.empty_normalise(
            instanceid=instanceid,
            type=device.attrs.matrix_effect,
            palette_count=device.attrs.palette_count,
            palette=device.attrs.palette,
            parameters={},
        )

    def make_device_chain(self, device):
        return TileMessages.StateDeviceChain(
            start_index=0,
            tile_devices_count=len(device.attrs.chain),
            tile_devices=[c.as_dict() for c, _ in device.attrs.chain],
        )

    def make_state_64s(self, device, pkt):
        for i in range(pkt.tile_index, pkt.tile_index + pkt.length):
            if i < len(device.attrs.chain):
                chain, colors = device.attrs.chain[i]
                yield TileMessages.State64(
                    tile_index=i, x=0, y=0, width=chain.width, colors=list(colors)
                )


class ZonesResponder(Responder):
    _fields = ["zones", ("zones_effect", lambda: MultiZoneEffectType.OFF)]

    def has_multizone(self, device):
        return ProductResponder.capability(device).has_multizone

    def has_extended_multizone(self, device):
        return ProductResponder.capability(device).has_extended_multizone

    def validate_attr(self, device, field, val):
        if field == "zones" and len(val) > 82:
            raise PhotonsAppError("Can only have up to 82 zones!")

    async def reset(self, device, *, zero=False):
        if self.has_multizone(device):
            await super().reset(device, zero=zero)

    def effect_response(self, device):
        return MultiZoneMessages.StateMultiZoneEffect(type=device.attrs.zones_effect)

    def extended_multizone_response(self, device):
        return MultiZoneMessages.StateExtendedColorZones(
            zones_count=len(device.attrs.zones),
            zone_index=0,
            colors_count=len(device.attrs.zones),
            colors=[z.as_dict() for z in device.attrs.zones],
        )

    def multizone_responses(self, device):
        buf = []
        bufs = []

        for i, zone in enumerate(device.attrs.zones):
            if len(buf) == 8:
                bufs.append(buf)
                buf = []

            buf.append((i, zone))

        if buf:
            bufs.append(buf)

        for buf in bufs:
            yield MultiZoneMessages.StateMultiZone(
                zones_count=len(device.attrs.zones),
                zone_index=buf[0][0],
                colors=[b.as_dict() for _, b in buf],
            )

    def set_zone(self, device, index, hue, saturation, brightness, kelvin):
        if index >= len(device.attrs.zones):
            log.warning(
                hp.lc(
                    "Setting zone outside range of the device",
                    number_zones=len(device.attrs.zones),
                    want=index,
                )
            )
            return

        device.attrs.zones[index] = Color(hue, saturation, brightness, kelvin)

    async def respond(self, device, pkt, source):
        if not self.has_multizone(device):
            return

        if pkt | MultiZoneMessages.SetMultiZoneEffect:
            res = self.effect_response(device)
            device.attrs.zones_effect = pkt.type
            yield res
        elif pkt | MultiZoneMessages.GetMultiZoneEffect:
            yield self.effect_response(device)

        elif pkt | MultiZoneMessages.GetColorZones:
            if pkt.start_index != 0 or pkt.end_index != 255:
                raise PhotonsAppError(
                    "Fake device only supports getting all color zones", got=pkt.payload
                )

            for r in self.multizone_responses(device):
                yield r
        elif pkt | MultiZoneMessages.SetColorZones:
            res = []
            for r in self.multizone_responses(device):
                res.append(r)
            for i in range(pkt.start_index, pkt.end_index + 1):
                self.set_zone(device, i, pkt.hue, pkt.saturation, pkt.brightness, pkt.kelvin)

            for r in res:
                yield r

        if self.has_extended_multizone(device):
            if pkt | MultiZoneMessages.GetExtendedColorZones:
                yield self.extended_multizone_response(device)

            elif pkt | MultiZoneMessages.SetExtendedColorZones:
                res = self.extended_multizone_response(device)
                for i, c in enumerate(pkt.colors[: pkt.colors_count]):
                    self.set_zone(
                        device, i + pkt.zone_index, c.hue, c.saturation, c.brightness, c.kelvin
                    )
                yield res


class GroupingResponder(Responder):
    _fields = [
        ("group_uuid", lambda: ""),
        ("group_label", lambda: ""),
        ("group_updated_at", lambda: 0),
        ("location_uuid", lambda: ""),
        ("location_label", lambda: ""),
        ("location_updated_at", lambda: 0),
    ]

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetGroup:
            yield self.make_group_state(device)

        elif pkt | DeviceMessages.SetGroup:
            device.attrs.group_uuid = pkt.group
            device.attrs.group_label = pkt.label
            device.attrs.group_updated_at = pkt.updated_at
            yield self.make_group_state(device)

        elif pkt | DeviceMessages.GetLocation:
            yield self.make_location_state(device)

        elif pkt | DeviceMessages.SetLocation:
            device.attrs.location_uuid = pkt.location
            device.attrs.location_label = pkt.label
            device.attrs.location_updated_at = pkt.updated_at
            yield self.make_location_state(device)

    def make_group_state(self, device):
        return DeviceMessages.StateGroup(
            group=device.attrs.group_uuid,
            label=device.attrs.group_label,
            updated_at=device.attrs.group_updated_at,
        )

    def make_location_state(self, device):
        return DeviceMessages.StateLocation(
            location=device.attrs.location_uuid,
            label=device.attrs.location_label,
            updated_at=device.attrs.location_updated_at,
        )


class Firmware(dictobj):
    fields = ["major", "minor", "build", ("install", 0)]


class ProductResponder(Responder):
    _fields = ["product", "vendor_id", "product_id", "firmware"]

    @classmethod
    def from_product(self, product, firmware=Firmware(0, 0, 0)):
        return ProductResponder(
            product=product, product_id=product.pid, vendor_id=product.vendor.vid, firmware=firmware
        )

    @classmethod
    def capability(kls, device):
        assert any(isinstance(r, kls) for r in device.responders)
        return device.attrs.product.cap(device.attrs.firmware.major, device.attrs.firmware.minor)

    async def respond(self, device, pkt, source):
        if pkt | DeviceMessages.GetVersion:
            yield DeviceMessages.StateVersion(
                vendor=device.attrs.vendor_id, product=device.attrs.product_id, version=0
            )

        elif pkt | DeviceMessages.GetHostFirmware:
            yield DeviceMessages.StateHostFirmware(
                build=device.attrs.firmware.build,
                version_major=device.attrs.firmware.major,
                version_minor=device.attrs.firmware.minor,
            )

        elif pkt | DeviceMessages.GetWifiFirmware:
            yield DeviceMessages.StateWifiFirmware(build=0, version_major=0, version_minor=0)


def default_responders(
    product=Products.LCM2_A19,
    *,
    power=0,
    label="",
    color=Color(0, 1, 1, 3500),
    infrared=0,
    zones=None,
    firmware=Firmware(0, 0, 0),
    zones_effect=MultiZoneEffectType.OFF,
    matrix_effect=TileEffectType.OFF,
    chain=None,
    chain_length=5,
    matrix_width=8,
    matrix_height=8,
    group_uuid="",
    group_label="",
    group_updated_at=0,
    location_uuid="",
    location_label="",
    location_updated_at=0,
    **kwargs,
):
    product_responder = ProductResponder.from_product(product, firmware)

    responders = [
        product_responder,
        LightStateResponder(power=power, color=color, label=label),
        GroupingResponder(
            group_uuid=group_uuid,
            group_label=group_label,
            group_updated_at=group_updated_at,
            location_uuid=location_uuid,
            location_label=location_label,
            location_updated_at=location_updated_at,
        ),
    ]

    cap = product.cap(firmware_major=firmware.major, firmware_minor=firmware.minor)

    if cap.has_ir or cap.product.family is Family.LCM3:
        responders.append(InfraredResponder(infrared=infrared))

    meta = Meta.empty()

    if cap.has_multizone:
        if zones is None:
            assert False, "Product has multizone capability but no zones specified"
        zones_effect = enum_spec(None, MultiZoneEffectType, unpacking=True).normalise(
            meta, zones_effect
        )
        responders.append(ZonesResponder(zones=zones, zones_effect=zones_effect))

    if cap.has_matrix:
        kw = {"matrix_width": matrix_width, "matrix_height": matrix_height}
        if not cap.has_chain:
            kw["chain_length"] = 1

        kw["matrix_effect"] = enum_spec(None, TileEffectType, unpacking=True).normalise(
            meta, matrix_effect
        )

        if chain:
            kw["chain"] = chain

        responders.append(MatrixResponder(**kw))

    return responders


class MemoryTargetRunner:
    def __init__(self, final_future, devices):
        options = {
            "devices": devices,
            "final_future": final_future,
            "protocol_register": protocol_register,
        }
        self.target = MemoryTarget.create(options)
        self.devices = devices

    async def __aenter__(self):
        await self.start()

    async def start(self):
        for device in self.devices:
            await device.start()
        self.sender = await self.target.make_sender()

    async def __aexit__(self, typ, exc, tb):
        await self.close()

    async def close(self):
        await self.target.close_sender(self.sender)
        for device in self.target.devices:
            await device.finish()

    async def reset_devices(self):
        for device in self.devices:
            await device.reset()

    @property
    def serials(self):
        return [device.serial for device in self.devices]


def with_runner(func):
    async def test(s, **kwargs):
        final_future = asyncio.Future()
        try:
            runner = MemoryTargetRunner(final_future, s.devices, **kwargs)
            async with runner:
                await s.wait_for(func(s, runner))
        finally:
            final_future.cancel()
            await runner.reset_devices()

    test.__name__ = func.__name__
    return test


class ModuleLevelRunner:
    def __init__(self, *args, **kwargs):
        self.old_loop = asyncio.get_event_loop()
        self.loop = asyncio.new_event_loop()

        self.args = args
        self.kwargs = kwargs

    async def server_runner(self, devices, **kwargs):
        final_future = asyncio.Future()
        runner = MemoryTargetRunner(final_future, devices, **kwargs)
        await runner.start()

        async def close():
            final_future.cancel()
            await runner.close()

        return runner, close

    def setUp(self):
        """
        Set the loop to our loop and use ``serve_runner`` to get a runner and
        closer
        """
        asyncio.set_event_loop(self.loop)
        self.runner, self.closer = self.loop.run_until_complete(
            self.server_runner(*self.args, **self.kwargs)
        )

    def tearDown(self):
        """
        Call our closer function returned from ``server_runner`` and set close
        our loop
        """
        if self.closer is not None:
            self.loop.run_until_complete(self.closer())
        self.loop.close()
        asyncio.set_event_loop(self.old_loop)

    def test(self, func):
        async def test(s):
            await self.runner.reset_devices()
            await s.wait_for(func(s, self.runner), timeout=10)

        test.__name__ = func.__name__
        return test
