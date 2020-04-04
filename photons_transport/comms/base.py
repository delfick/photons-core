from photons_transport.errors import FailedToFindDevice
from photons_transport.comms.receiver import Receiver
from photons_transport.comms.waiter import Waiter
from photons_transport.comms.writer import Writer

from photons_app.errors import TimedOut, FoundNoDevices, RunErrors, BadRunWithResults
from photons_app import helpers as hp

from photons_protocol.packets import Information
from photons_protocol.messages import Messages

import binascii
import logging
import asyncio
import struct
import random
import json

log = logging.getLogger("photons_transport.comms")


class FakeAck:
    represents_ack = True

    __slots__ = ["source", "sequence", "target", "serial", "Information"]

    def __init__(self, source, sequence, target, serial, addr):
        self.serial = serial
        self.target = target
        self.source = source
        self.sequence = sequence
        self.Information = Information(remote_addr=addr)

    def __or__(self, kls):
        return kls.Payload.Meta.protocol == 1024 and kls.Payload.represents_ack

    def __repr__(self):
        return f"<ACK source: {self.source}, sequence: {self.sequence}, serial: {self.serial}>"


class Found:
    def __init__(self):
        self.found = {}

    def clone(self):
        found = self.__class__()
        for serial, services in self.found.items():
            found[serial] = dict(services)
        return found

    def cleanse_serial(self, serial):
        if isinstance(serial, str):
            serial = binascii.unhexlify(serial)
        return serial[:6]

    @property
    def serials(self):
        return sorted([binascii.hexlify(target).decode() for target in self.found])

    def __len__(self):
        return len(self.found)

    def __getitem__(self, serial):
        return self.found[self.cleanse_serial(serial)]

    def __setitem__(self, serial, value):
        serial = self.cleanse_serial(serial)
        self.found[serial] = value

    def __delitem__(self, serial):
        serial = self.cleanse_serial(serial)
        del self.found[serial]

    def __contains__(self, serial):
        serial = self.cleanse_serial(serial)
        return serial in self.found and self.found[serial]

    def __eq__(self, other):
        return self.found == other.found

    def __bool__(self):
        return bool(self.found)

    def borrow(self, other_found, session):
        if isinstance(other_found, Found):
            for target in other_found:
                if target not in self:
                    self[target] = {}
                for service, transport in other_found[target].items():
                    if service not in self[target]:
                        self[target][service] = transport.clone_for(session)

    async def remove_lost(self, found_now):
        found_now = [self.cleanse_serial(serial) for serial in found_now]

        for target in list(self):
            if target not in found_now:
                for transport in self[target].values():
                    try:
                        await transport.close()
                    except Exception as error:
                        log.error(hp.lc("Failed to close transport", error=error))
                del self[target]

    def __iter__(self):
        return iter(self.found)

    def __repr__(self):
        services = json.dumps(
            {
                binascii.hexlify(t).decode(): ",".join(repr(s) for s in services.keys())
                for t, services in self.found.items()
            }
        )
        return f"<FOUND: {services}>"


def timeout_task(task, errf, serial):
    """Used to cancel sending a messages and record a timed out exception"""
    if not task.done():
        if not errf.done():
            errf.set_exception(TimedOut("Waiting for reply to a packet", serial=serial))
        task.cancel()


class NoLimit:
    """Used when we don't have a limit semaphore to impose no limit on concurrent access"""

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def acquire(self):
        pass

    def release(self):
        pass

    def locked(self):
        return False


class Sender:
    def __init__(self, session, msg, reference, **kwargs):
        self.msg = msg
        self.kwargs = kwargs
        self.session = session
        self.reference = reference

        if "session" in self.kwargs:
            self.kwargs.pop("session")

        self.script = self.session.transport_target.script(msg)

    def __await__(self):
        return (yield from self.all_packets().__await__())

    async def all_packets(self):
        results = []
        try:
            async for pkt in self:
                results.append(pkt)
        except asyncio.CancelledError:
            raise
        except RunErrors as error:
            raise BadRunWithResults(results=results, _errors=error.errors)
        except Exception as error:
            raise BadRunWithResults(results=results, _errors=[error])
        else:
            return results

    def __aiter__(self):
        return self.stream_packets()

    async def stream_packets(self):
        async for pkt in self.script.run_with(self.reference, self.session, **self.kwargs):
            yield pkt


class Communication:
    _merged_options_formattable = True

    def __init__(self, target):
        self.transport_target = target

        self.found = Found()
        self.stop_fut = hp.ChildOfFuture(self.transport_target.final_future)
        self.receiver = Receiver()
        self.received_data_tasks = []

        self.setup()

    def setup(self):
        pass

    def __call__(self, msg, reference=None, **kwargs):
        return Sender(self, msg, reference, **kwargs)

    async def finish(self):
        self.stop_fut.cancel()
        for serial in self.found.serials:
            try:
                await self.forget(serial)
            except Exception as error:
                log.error(hp.lc("Failed to close transport", error=error, serial=serial))

        if self.received_data_tasks:
            for t in self.received_data_tasks:
                t.cancel()
            await asyncio.wait(self.received_data_tasks)

    @hp.memoized_property
    def source(self):
        """Return us a source to use for our packets"""
        return random.randrange(1, 1 << 32)

    def seq(self, target):
        """Create the next sequence for this target"""
        if not hasattr(self, "_seq"):
            self._seq = {}
        if target not in self._seq:
            self._seq[target] = 0
        self._seq[target] = (self._seq[target] + 1) % pow(2, 8)
        return self._seq[target]

    async def forget(self, serial):
        if serial not in self.found:
            return

        services = self.found[serial]
        del self.found[serial]

        for service, transport in services.items():
            try:
                await transport.close()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                log.error(
                    hp.lc("Failed to close transport", service=service, error=error, serial=serial)
                )

    async def add_service(self, serial, service, **kwargs):
        new = await self.make_transport(serial, service, kwargs)

        if serial not in self.found:
            self.found[serial] = {}

        existing = self.found[serial].get(service)

        if existing != new:
            if existing:
                try:
                    await existing.close()
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    log.error(
                        hp.lc(
                            "Failed to close old transport",
                            service=service,
                            error=error,
                            serial=serial,
                        )
                    )

            self.found[serial][service] = new

    async def find_devices(self, *, ignore_lost=False, raise_on_none=False, **kwargs):
        """Hook for finding devices"""
        kwargs["ignore_lost"] = ignore_lost
        kwargs["raise_on_none"] = raise_on_none
        found, _ = await self.find_specific_serials(None, **kwargs)
        return found

    async def find_specific_serials(
        self, serials, ignore_lost=False, raise_on_none=False, **kwargs
    ):
        kwargs["ignore_lost"] = ignore_lost
        kwargs["raise_on_none"] = raise_on_none
        found = await self._find_specific_serials(serials, **kwargs)
        missing = [] if serials is None else [serial for serial in serials if serial not in found]

        if missing:
            log.error(hp.lc("Didn't find some devices", missing=missing))

        return found, missing

    async def _find_specific_serials(
        self, serials, ignore_lost=False, raise_on_none=False, timeout=60, **kwargs
    ):
        found_now = await self._do_search(serials, timeout, **kwargs)

        if not ignore_lost:
            await self.found.remove_lost(found_now)

        if serials is None and not found_now:
            if raise_on_none:
                raise FoundNoDevices()
            else:
                log.error(hp.lc("Didn't find any devices"))

        return self.found

    async def _do_search(self, serials, timeout, **kwargs):
        raise NotImplementedError()

    async def make_transport(self, serial, service, kwargs):
        raise NotImplementedError()

    async def choose_transport(self, packet, services):
        raise NotImplementedError()

    async def make_broadcast_transport(self, broadcast):
        raise NotImplementedError()

    def retry_options_for(self, packet, transport):
        raise NotImplementedError()

    async def broadcast(self, packet, broadcast, **kwargs):
        kwargs["transport"] = await self.make_broadcast_transport(broadcast)
        kwargs["is_broadcast"] = True
        return await self.send_single(packet, **kwargs)

    async def send_single(
        self,
        original,
        packet,
        *,
        timeout,
        limit=None,
        no_retry=False,
        transport=None,
        broadcast=False,
        connect_timeout=10,
    ):

        transport, is_broadcast = await self._transport_for_send(
            transport, packet, original, broadcast, connect_timeout
        )

        retry_options = self.retry_options_for(original, transport)

        writer = Writer(
            self,
            transport,
            self.receiver,
            original,
            packet,
            retry_options,
            did_broadcast=is_broadcast,
            connect_timeout=connect_timeout,
        )

        waiter = Waiter(self.stop_fut, writer, retry_options, no_retry=no_retry)

        try:
            return await self._get_response(packet, timeout, waiter, limit=limit)
        finally:
            waiter.cancel()

    async def _transport_for_send(self, transport, packet, original, broadcast, connect_timeout):
        is_broadcast = bool(broadcast)

        if transport is None and (is_broadcast or packet.target is None):
            is_broadcast = True
            transport = await self.make_broadcast_transport(broadcast or True)

        if transport is None:
            if packet.serial not in self.found:
                raise FailedToFindDevice(serial=packet.serial)

            transport = await self.choose_transport(original, self.found[packet.serial])

        await transport.spawn(original, timeout=connect_timeout)
        return transport, is_broadcast

    def sync_received_data(self, *args, **kwargs):
        task = hp.async_as_background(self.received_data(*args, **kwargs))
        self.received_data_tasks.append(task)
        return task

    async def received_data(self, data, addr, allow_zero=False):
        """What to do when we get some data"""
        if type(data) is bytes:
            log.debug(hp.lc("Received bytes", bts=binascii.hexlify(data).decode()))

        try:
            protocol_register = self.transport_target.protocol_register
            protocol, pkt_type, Packet, PacketKls, data = Messages.get_packet_type(
                data, protocol_register
            )

            if protocol == 1024 and pkt_type == 45:
                source = struct.unpack("<I", data[4:8])[0]
                target = data[8:16]
                sequence = data[23]

                serial = binascii.hexlify(target[:6]).decode()
                pkt = FakeAck(source, sequence, target, serial, addr)
            else:
                if PacketKls is None:
                    PacketKls = Packet
                pkt = PacketKls.unpack(data)
        except Exception as error:
            log.exception(error)
        else:
            await self.receiver.recv(pkt, addr, allow_zero=allow_zero)

    async def _get_response(self, packet, timeout, waiter, limit=None):
        errf = hp.ResettableFuture()
        errf.add_done_callback(hp.silent_reporter)

        response = []

        async def wait_for_responses():
            async with (limit or NoLimit()):
                if hasattr(asyncio, "current_task"):
                    current_task = asyncio.current_task()
                else:
                    current_task = asyncio.Task.current_task()

                asyncio.get_event_loop().call_later(
                    timeout, timeout_task, current_task, errf, packet.serial
                )

                try:
                    for info in await waiter:
                        response.append(info)
                finally:
                    if hasattr(waiter, "finish"):
                        await waiter.finish()

        f = hp.async_as_background(wait_for_responses(), silent=True)

        def process(res):
            if errf.done() and not errf.cancelled():
                # Errf has an exception
                return

            elif res.cancelled():
                errf.reset()
                errf.set_exception(TimedOut("Message was cancelled", serial=packet.serial))
                return

            if not res.cancelled():
                exc = res.exception()
                if exc:
                    errf.set_exception(exc)
                    return

            errf.set_result(True)

        f.add_done_callback(process)

        try:
            await errf
        finally:
            f.cancel()

        return response
