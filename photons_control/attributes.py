"""
.. autofunction:: make_color

.. autofunction:: make_colors
"""
from photons_control.planner import Skip

from photons_app.actions import an_action
from photons_app.errors import BadOption


from delfick_project.norms import sb, Meta
import sys


def find_packet(protocol_register, value, prefix):
    """
    Return either None or the class object for this value/prefix combination.

    For example, if value is GetHostFirmware then the GetHostFirmware packet is returned

    If the value is host_firmware or HostFirmware, then we get GetHostFirmware if the prefix is Get and SetHostFirmware if the prefix is Set
    """
    prefix = prefix.lower().capitalize()

    kls_name_plain = f"{prefix}{value}"
    kls_name_transformed = f"""{prefix}{"".join(part.capitalize() for part in value.split("_"))}"""

    for messages in protocol_register.message_register(1024):
        for kls in messages.by_type.values():
            if kls.__name__ in (value, kls_name_plain, kls_name_transformed):
                return kls


@an_action(special_reference=True, needs_target=True)
async def attr(collector, target, reference, artifact, **kwargs):
    """
    Send a message to your bulb and print out all the replies.

    This is the same as the get_attr and set_attr commands but doesn't prefix the wanted message with get or set

    ``target:attr d073d5000000 get_host_firmware``
    """
    protocol_register = collector.configuration["protocol_register"]

    if artifact in (None, "", sb.NotSpecified):
        raise BadOption(
            "Please specify what you want to get\nUsage: {0} <target>:get_attr <reference> <attr_to_get>".format(
                sys.argv[0]
            )
        )

    kls = find_packet(protocol_register, artifact, "")
    if kls is None:
        raise BadOption("Sorry, couldn't a class for this message", prefix="", want=artifact)

    photons_app = collector.photons_app

    extra = photons_app.extra_as_json

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    msg = kls.normalise(Meta.empty(), extra)
    async for pkt in target.send(msg, reference, **kwargs):
        print("{0}: {1}".format(pkt.serial, repr(pkt.payload)))


@an_action(special_reference=True, needs_target=True)
async def attr_actual(collector, target, reference, artifact, **kwargs):
    """
    Same as the attr command but prints out the actual values on the replies rather than transformed values
    """
    protocol_register = collector.configuration["protocol_register"]

    if artifact in (None, "", sb.NotSpecified):
        raise BadOption(
            "Please specify what you want to get\nUsage: {0} <target>:get_attr <reference> <attr_to_get>".format(
                sys.argv[0]
            )
        )

    kls = find_packet(protocol_register, artifact, "")
    if kls is None:
        raise BadOption("Sorry, couldn't a class for this message", prefix="", want=artifact)

    extra = collector.photons_app.extra_as_json

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    def lines(pkt, indent="    "):
        for field in pkt.Meta.all_names:
            val = pkt[field]
            if isinstance(val, list):
                yield f"{indent}{field}:"
                for item in val:
                    ind = f"{indent}    "
                    ls = list(lines(item, ind))
                    first = list(ls[0])
                    first[len(indent) + 2] = "*"
                    ls[0] = "".join(first)
                    yield from ls
            else:
                yield f"{indent}{field}: {pkt.actual(field)}"

    msg = kls.normalise(Meta.empty(), extra)
    async for pkt in target.send(msg, reference, **kwargs):
        print()
        print(f"""{"=" * 10}: {pkt.serial}""")
        for line in lines(pkt):
            print(line)


@an_action(special_reference=True, needs_target=True)
async def get_attr(collector, target, reference, artifact, **kwargs):
    """
    Get attributes from your globes

    ``target:get_attr d073d5000000 color``

    Where ``d073d5000000`` is replaced with the serial of the device you are
    addressing and ``color`` is replaced with the attribute you want.

    This task works by looking at all the loaded LIFX binary protocol messages
    defined for the 1024 protocol and looks for ``Get<Attr>``.

    So if you want the ``color`` attribute, it will look for the ``GetColor``
    message and send that to the device and print out the reply packet we get
    back.
    """
    protocol_register = collector.configuration["protocol_register"]

    if artifact in (None, "", sb.NotSpecified):
        raise BadOption(
            "Please specify what you want to get\nUsage: {0} <target>:get_attr <reference> <attr_to_get>".format(
                sys.argv[0]
            )
        )

    getter = find_packet(protocol_register, artifact, "Get")
    if getter is None:
        raise BadOption("Sorry, couldn't a class for this message", prefix="get", want=artifact)

    extra = collector.photons_app.extra_as_json

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    msg = getter.normalise(Meta.empty(), extra)
    async for pkt in target.send(msg, reference, **kwargs):
        print("{0}: {1}".format(pkt.serial, repr(pkt.payload)))


@an_action(special_reference=True, needs_target=True)
async def set_attr(collector, target, reference, artifact, broadcast=False, **kwargs):
    """
    Set attributes on your globes

    ``target:set_attr d073d5000000 color -- '{"hue": 360, "saturation": 1, "brightness": 1}'``

    This does the same thing as ``get_attr`` but will look for ``Set<Attr>``
    message and initiates it with the options found after the ``--``.

    So in this case it will create ``SetColor(hue=360, saturation=1, brightness=1)``
    and send that to the device.
    """
    protocol_register = collector.configuration["protocol_register"]

    if artifact in (None, "", sb.NotSpecified):
        raise BadOption(
            "Please specify what you want to get\nUsage: {0} <target>:set_attr <reference> <attr_to_get> -- '{{<options>}}'".format(
                sys.argv[0]
            )
        )

    setter = find_packet(protocol_register, artifact, "Set")
    if setter is None:
        raise BadOption("Sorry, couldn't a class for this message", prefix="set", want=artifact)

    extra = collector.photons_app.extra_as_json

    if "extra_payload_kwargs" in kwargs:
        extra.update(kwargs["extra_payload_kwargs"])

    msg = setter.normalise(Meta.empty(), extra)
    async for pkt in target.send(msg, reference, broadcast=broadcast):
        print("{0}: {1}".format(pkt.serial, repr(pkt.payload)))


@an_action(needs_target=True, special_reference=True)
async def get_effects(collector, target, reference, **kwargs):
    async with target.session() as sender:
        plans = sender.make_plans("firmware_effects")

        async for serial, _, info in sender.gatherer.gather(plans, reference):
            if info is Skip:
                continue

            print(f"{serial}: {info['type']}")
            for field, value in info["options"].items():
                if field == "palette":
                    if value:
                        print("\tpalette:")
                        for c in value:
                            print(f"\t\t{repr(c)}")
                else:
                    print(f"\t{field}: {value}")
            print()
