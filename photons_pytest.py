"""pytest-cov: avoid already-imported warning: PYTEST_DONT_REWRITE."""

__shortdesc__ = "Helpers for writing tests for photons in pytest"

from textwrap import dedent
from unittest import mock
import tempfile
import asyncio
import socket
import shutil
import time
import sys
import re
import os

try:
    import pytest
except:

    class FakePytest:
        class fixture:
            def __init__(self, **kwargs):
                pass

            def __call__(self, func):
                return func

    pytest = FakePytest()


def _port_connected(port):
    """
    Return whether something is listening on this port
    """
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def run_pytest():
    class EditConfig:
        @pytest.hookimpl(hookwrapper=True)
        def pytest_cmdline_parse(pluginmanager, args):
            args.extend(
                [
                    "--tb=short",
                    "-o",
                    "console_output_style=classic",
                    "-o",
                    "default_alt_async_timeout=1",
                    "-W",
                    "ignore:Using or importing the ABCs:DeprecationWarning",
                    "--log-level=INFO",
                    "-p",
                    "helpers_namespace",
                ]
            )
            yield

    sys.exit(pytest.main(plugins=[EditConfig()]))


regexes = {}


@pytest.fixture(scope="session")
def a_temp_dir():
    class TempDir:
        def __enter__(self):
            self.d = tempfile.mkdtemp()
            return self.d, self.make_file

        def __exit__(self, exc_type, exc, tb):
            if hasattr(self, "d") and os.path.exists(self.d):
                shutil.rmtree(self.d)

        def make_file(self, name, contents):
            location = os.path.join(self.d, name)
            parent = os.path.dirname(location)
            if not os.path.exists(parent):
                os.makedirs(parent)

            with open(location, "w") as fle:
                fle.write(dedent(contents))

            return location

    return TempDir


@pytest.fixture(scope="session")
def FakeTime():
    class FakeTime:
        def __init__(self, mock_sleep=False, mock_async_sleep=False):
            self.time = 0
            self.patches = []
            self.mock_sleep = mock_sleep
            self.mock_async_sleep = mock_async_sleep

        def set(self, t):
            self.time = t

        def add(self, t):
            self.time += t

        def __enter__(self):
            self.patches.append(mock.patch("time.time", self))

            if self.mock_sleep:
                self.patches.append(mock.patch("time.sleep", self.sleep))
            if self.mock_async_sleep:
                self.patches.append(mock.patch("asyncio.sleep", self.async_sleep))

            for p in self.patches:
                p.start()

            return self

        def __exit__(self, exc_type, exc, tb):
            for p in self.patches:
                p.stop()

        def __call__(self):
            return self.time

        def sleep(self, amount):
            self.add(amount)

        async def async_sleep(self, amount):
            self.add(amount)
            await asyncio.sleep(0.001)

    return FakeTime


def pytest_configure(config):
    config.addinivalue_line("markers", "focus: mark test to run")

    if not hasattr(pytest, "helpers"):
        return

    @pytest.helpers.register
    def assert_regex(regex, value):
        __tracebackhide__ = True

        if isinstance(regex, str):
            if regex not in regexes:
                regexes[regex] = re.compile(regex)
            regex = regexes[regex]

        m = regex.match(value)
        if m:
            return

        def indented(v):
            return "\n".join(f"  {line}" for line in v.split("\n"))

        lines = [
            "Regex didn't match",
            "Wanted:\n",
            indented(regex.pattern),
            "\nto match:",
            indented(value),
        ]

        pytest.fail("\n".join(lines))

    @pytest.helpers.register
    def free_port():
        """
        Return an unused port number
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            return s.getsockname()[1]

    @pytest.helpers.register
    async def wait_for_port(port, timeout=3, gap=0.01):
        """
        Wait for a port to have something behind it
        """
        start = time.time()
        while time.time() - start < timeout:
            if _port_connected(port):
                break
            await asyncio.sleep(gap)
        assert _port_connected(port)

    @pytest.helpers.register
    def port_connected(port):
        return _port_connected(port)

    @pytest.helpers.register
    def AsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("asynctest.mock").mock.CoroutineMock(*args, **kwargs)
        else:
            return mock.AsyncMock(*args, **kwargs)

    @pytest.helpers.register
    def MagicAsyncMock(*args, **kwargs):
        if sys.version_info < (3, 8):
            return __import__("asynctest").MagicMock(*args, **kwargs)
        else:
            return mock.MagicMock(*args, **kwargs)


class MemoryDevicesRunner:
    def __init__(self, devices):
        self.final_future = asyncio.Future()
        options = {
            "devices": devices,
            "final_future": self.final_future,
            "protocol_register": __import__("photons_messages").protocol_register,
        }

        MemoryTarget = __import__("photons_transport.targets").targets.MemoryTarget
        self.target = MemoryTarget.create(options)
        self.devices = devices

    async def __aenter__(self):
        for device in self.devices:
            await device.start()

        self.sender = await self.target.make_sender()
        return self

    async def __aexit__(self, typ, exc, tb):
        if hasattr(self, "sender"):
            await self.target.close_sender(self.sender)

        for device in self.target.devices:
            await device.finish()

        self.final_future.cancel()

    async def reset_devices(self):
        for device in self.devices:
            await device.reset()

    async def per_test(self):
        await self.reset_devices()

    @property
    def serials(self):
        return [device.serial for device in self.devices]


@pytest.fixture(scope="session")
def memory_devices_runner():
    return MemoryDevicesRunner
