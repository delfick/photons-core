"""Some useful, common helper functionalities"""

from photons_app.errors import PhotonsAppError

from delfick_project.logging import lc
from contextlib import contextmanager
from queue import Queue, Empty
from functools import wraps
import threading
import tempfile
import asyncio
import logging
import uuid
import time
import sys
import os

log = logging.getLogger("photons_app.helpers")

# Make vim be quiet
lc = lc

if hasattr(asyncio, "exceptions"):
    InvalidStateError = asyncio.exceptions.InvalidStateError
else:
    InvalidStateError = asyncio.futures.InvalidStateError


class Nope:
    """Used to say there was no value"""

    pass


class ATicker:
    def __init__(self, every, final_future=None):
        self.every = every
        self.tick_fut = ResettableFuture()
        self.last_tick = None
        self.final_future = final_future or asyncio.Future()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.final_future.done():
            raise StopAsyncIteration

        if self.last_tick is None:
            self.last_tick = time.time()
            return

        self.change_after(self.every)
        await asyncio.wait([self.tick_fut, self.final_future], return_when=asyncio.FIRST_COMPLETED)

        if self.final_future.done():
            raise StopAsyncIteration

        self.tick_fut.reset()
        self.last_tick = time.time()

    def change_after(self, every, *, set_new_every=True):
        if set_new_every:
            self.every = every

        current = self.last_tick
        diff = every - (time.time() - self.last_tick)

        if diff == 0:
            self.tick_fut.reset()
            self.tick_fut.set_result(True)
        else:

            def reset():
                if self.last_tick == current:
                    self.tick_fut.reset()
                    self.tick_fut.set_result(True)

            asyncio.get_event_loop().call_later(diff, reset)


async def tick(every, *, final_future=None):
    async for _ in ATicker(every, final_future=final_future):
        yield


class TaskHolder:
    """
    An object for managing asynchronous coroutines.

    Usage looks like:

    .. code-block:: python

        final_future = asyncio.Future()

        async def something():
            await asyncio.sleep(5)

        with TaskHolder(final_future) as ts:
            ts.add(something())
            ts.add(something())

    Once the context manager is exited you may still run ts.add and the context
    manager will stay alive until all coroutines have finished.

    If you complete final_future before all the tasks have completed then the
    tasks will be cancelled and properly waited on so their finally blocks run
    before the context manager finishes.

    ts.add will also return the task object that is made from the coroutine.

    ts.add also takes a ``silent=False`` parameter, that when True will not log
    any errors that happen. Otherwise errors will be logged.
    """

    def __init__(self, final_future):
        self.ts = []
        self.final_future = final_future

    def add(self, coro, silent=False):
        return self.add_task(async_as_background(coro, silent=silent))

    def add_task(self, task, silent=False):
        self.ts.append(task)
        self.ts = [t for t in self.ts if not t.done()]
        return task

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.finish()

    async def finish(self):
        while any(not t.done() for t in self.ts):
            for t in self.ts:
                if self.final_future.done():
                    t.cancel()

            if self.ts:
                return_when = (
                    asyncio.ALL_COMPLETED if self.final_future.done() else asyncio.FIRST_COMPLETED
                )
                await asyncio.wait([self.final_future, *self.ts], return_when=return_when)

        if self.ts:
            await asyncio.wait(self.ts)


class ResultStreamer:
    """
    An async generator you can add tasks to and results will be streamed as they
    become available.

    To use this, you first create a streamer and give it a ``final_future`` and
    ``error_catcher``. If the ``final_future`` is cancelled, then the streamer
    will stop and any tasks it knows about will be cancelled.

    The ``error_catcher`` is a standard Photons error_catcher. If it's a list
    then exceptions will be added to it. If it's a function then it will be
    called with exceptions. Otherwise it is ignored. Note that if you don't
    specify ``exceptions_only_to_error_catcher=True`` then result objects will
    be given to the ``error_catcher`` rather than the exceptions themselves.

    Once you have a streamer you add tasks, coroutines or async generators
    to the streamer. Once you have no more of these to add to the streamer then
    you call ``streamer.no_more_work()`` so that when all remaining tasks have
    finished, the streamer will stop iterating results.

    The streamer will yield ``ResultStreamer.Result`` objects that contain
    the ``value`` from the task, a ``context`` object that you give to the
    streamer when you register a task and a ``successful`` boolean that is False
    when the result was from an exception.

    When you register a task/coroutine/generator you may specify an ``on_done``
    callback which will be called when it finishes. For tasks and coroutines
    this is called with the result from that task. For async generators it
    is either called with an exception Result if the generator did not exit
    successfully, or a success Result with a ``ResultStreamer.GeneratorComplete``
    instance.

    When you add an async generator, you may specify an ``on_each`` function
    that will be called for each value that is yielded from the generator.

    You may add tasks, coroutines and async generators while you are taking
    results from the streamer.

    For example:

    .. code-block:: python

        final_future = asyncio.Future()

        def error_catcher(error_result):
            print(error_result)

        streamer = ResultStreamer(final_future, error_catcher=error_catcher)

        async def coro_function():
            await something
            await streamer.add_generator(generator2, context=SomeContext())
            return 20

        async def coro_function2():
            return 42

        async def generator():
            for i in range(3):
                yield i
                await something_else
            await streamer.add_coroutine(coro_function2())

        await streamer.add_coroutine(coro_function(), context=20)
        await streamer.add_generator(coro_function())

        async with streamer:
            async for result in streamer:
                print(result.value, result.context, result.successful)

    If you don't want to use the ``async with streamer`` then you must call
    ``await streamer.finish()`` when you are done with the streamer to ensure
    everything is cleaned up.
    """

    class GeneratorComplete:
        pass

    class Result:
        def __init__(self, value, context, successful):
            self.value = value
            self.context = context
            self.successful = successful

        def __eq__(self, other):
            return (
                isinstance(other, self.__class__)
                and other.value == self.value
                and other.context == self.context
                and other.successful == self.successful
            )

        def __repr__(self):
            status = "success" if self.successful else "failed"
            return f"<Result {status}: {self.value}: {self.context}>"

    def __init__(self, final_future, *, error_catcher=None, exceptions_only_to_error_catcher=False):
        self.final_future = ChildOfFuture(final_future)
        self.error_catcher = error_catcher
        self.exceptions_only_to_error_catcher = exceptions_only_to_error_catcher

        self.ts = []
        self.generators = []

        self.queue = asyncio.Queue()
        self.stop_on_completion = False

    async def add_generator(self, gen, *, context=None, on_each=None, on_done=None):
        async def run():
            async for result in gen:
                result = self.Result(result, context, True)
                self.queue.put_nowait(result)
                if on_each:
                    on_each(result)
            return self.GeneratorComplete

        task = await self.add_coroutine(run(), context=context, on_done=on_done)

        if self.final_future.done():
            task.cancel()
            await asyncio.wait([task])
            await asyncio.wait([gen.aclose()])
            return task

        self.generators.append((task, gen))
        return task

    async def add_coroutine(self, coro, *, context=None, on_done=None):
        return await self.add_task(
            async_as_background(coro, silent=bool(self.error_catcher)),
            context=context,
            on_done=on_done,
        )

    async def add_task(self, task, *, context=None, on_done=None):
        if self.final_future.done():
            task.cancel()
            await asyncio.wait([task])
            return task

        def add_to_queue(res):
            successful = False

            if res.cancelled():
                exc = asyncio.CancelledError()
                value = asyncio.CancelledError()
            else:
                exc = res.exception()
                if exc:
                    value = exc
                else:
                    value = res.result()
                    successful = True

            result = self.Result(value, context, successful)

            if value is not self.GeneratorComplete:
                if not successful:
                    v = value if self.exceptions_only_to_error_catcher else result
                    add_error(self.error_catcher, v)

                self.queue.put_nowait(result)

            if on_done:
                on_done(result)

        task.add_done_callback(add_to_queue)
        self.ts.append(task)
        return task

    def no_more_work(self):
        self.stop_on_completion = True

    async def retrieve(self):
        while True:
            nxt = async_as_background(self.queue.get())
            await asyncio.wait([nxt, self.final_future], return_when=asyncio.FIRST_COMPLETED)

            if self.final_future.done():
                nxt.cancel()
                return

            yield (await nxt)

            self.ts = [t for t in self.ts if not t.done()]
            if self.stop_on_completion and not self.ts and self.queue.empty():
                return

            # Cleanup any finished generators
            new_gens = []
            for t, g in self.generators:
                if t.done():
                    await asyncio.wait([t])
                    await asyncio.wait([g.aclose()])
                else:
                    new_gens.append((t, g))
            self.generators = new_gens

    async def finish(self):
        self.final_future.cancel()

        wait_for = []
        second_after = []

        for t in self.ts:
            t.cancel()
            wait_for.append(t)

        for t, g in self.generators:
            t.cancel()
            wait_for.append(t)
            second_after.append(lambda: g.aclose())

        if wait_for:
            await asyncio.wait(wait_for)
        if second_after:
            await asyncio.wait([l() for l in second_after])

        self.queue.put_nowait(None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_typ, exc, tb):
        await self.finish()

    def __aiter__(self):
        return self.retrieve()


@contextmanager
def just_log_exceptions(log, *, reraise=None, message="Unexpected error"):
    """
    A context manager that will catch all exceptions and just call::

        log.error(message, exc_info=sys.exc_info())

    Any class in reraise that matches the error will result in re raising the error

    For example:

    .. code-block:: python

        import logging
        import asyncio

        log = logging.getLogger("my_example")

        message = "That's not meant to happen"

        with just_log_exceptions(log, reraise=[asyncio.CancelledError], message=message):
            await do_something()
    """
    try:
        yield
    except Exception as error:
        if reraise and any(isinstance(error, r) for r in reraise):
            raise
        log.error(message, exc_info=sys.exc_info())


def add_error(catcher, error):
    """
    Adds an error to an error_catcher.

    This means if it's callable we call it with the error

    and if it's a list or set we add the error to it.
    """
    if callable(catcher):
        catcher(error)
    elif type(catcher) is list:
        catcher.append(error)
    elif type(catcher) is set:
        catcher.add(error)


@contextmanager
def a_temp_file():
    """
    Yield the name of a temporary file and ensure it's removed after use

    .. code-block:: python

        with hp.a_temp_file() as fle:
            fle.write("hello")
            fle.flush()
            os.system("cat {0}".format(fle.name))
    """
    filename = None
    tmpfile = None
    try:
        tmpfile = tempfile.NamedTemporaryFile(delete=False)
        filename = tmpfile.name
        yield tmpfile
    finally:
        if tmpfile is not None:
            tmpfile.close()
        if filename and os.path.exists(filename):
            os.remove(filename)


def nested_dict_retrieve(data, keys, dflt):
    """
    Used to get a value deep in a nested dictionary structure

    For example

    .. code-block:: python

        data = {"one": {"two": {"three": "four"}}}

        nested_dict_retrieve(data, ["one", "two", "three"], 6) == "four"

        nested_dict_retrieve(data, ["one", "two"], 6) == {"three": "four"}

        nested_dict_retrieve(data, ["one", "four"], 6) == 6
    """
    if not keys:
        return data

    for key in keys[:-1]:
        if type(data) is not dict:
            return dflt

        if key not in data:
            return dflt

        data = data[key]

    if type(data) is not dict:
        return dflt

    last_key = keys[-1]
    if last_key not in data:
        return dflt

    return data[last_key]


def fut_has_callback(fut, callback):
    if not fut._callbacks:
        return False

    for cb in fut._callbacks:
        if type(cb) is tuple and cb:
            cb = cb[0]

        if cb == callback:
            return True

    return False


def async_as_normal(func):
    """
    Return a function that creates a task on the provided loop using the
    provided func and add reporter as a done callback

    .. code-block:: python

        # Define my async function
        async def my_func(a, b):
            await something(a, b)

        # Create a callable that will start the async function in the background
        func = hp.async_as_normal(my_func)

        # start the async job
        func(1, b=6)
    """

    @wraps(func)
    def normal(*args, **kwargs):
        coroutine = func(*args, **kwargs)
        t = asyncio.get_event_loop().create_task(coroutine)
        t.add_done_callback(reporter)
        return t

    return normal


def async_as_background(coroutine, silent=False):
    """
    Create a task with reporter as a done callback using provided loop and
    coroutine and return the new task.

    .. code-block:: python

        async def my_func():
            await something()

        # Kick off the function in the background
        hp.async_as_background(my_func())
    """
    t = asyncio.get_event_loop().create_task(coroutine)
    if silent:
        t.add_done_callback(silent_reporter)
    else:
        t.add_done_callback(reporter)
    return t


async def async_with_timeout(coroutine, timeout=10, timeout_error=None, silent=False):
    """
    Run a coroutine as a task until it's complete or times out

    If time runs out the task is cancelled

    If timeout_error is defined, that is raised instead of asyncio.CancelledError on timeout
    """
    f = asyncio.Future()
    t = async_as_background(coroutine, silent=silent)

    def pass_result(res):
        if res.cancelled():
            f.cancel()
            return

        if res.exception() is not None:
            if not f.done():
                f.set_exception(t.exception())
            return

        if t.done() and not f.done():
            f.set_result(t.result())

    t.add_done_callback(pass_result)

    def set_timeout():
        if not t.done():
            if timeout_error and not f.done():
                f.set_exception(timeout_error)

            t.cancel()
            f.cancel()

    asyncio.get_event_loop().call_later(timeout, set_timeout)
    return await f


class memoized_property(object):
    """
    Decorator to make a descriptor that memoizes it's value

    .. code-block:: python

        class MyClass(object):
            @hp.memoized_property
            def thing(self):
                return expensive_operation()

        obj = MyClass()

        # Get us the result of expensive operation
        print(obj.thing)

        # And we get the result again but minus the expensive operation
        print(obj.thing)
    """

    class Empty:
        pass

    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__
        self.cache_name = "_{0}".format(self.name)

    def __get__(self, instance=None, owner=None):
        if instance is None:
            return self

        if getattr(instance, self.cache_name, self.Empty) is self.Empty:
            setattr(instance, self.cache_name, self.func(instance))
        return getattr(instance, self.cache_name)

    def __set__(self, instance, value):
        setattr(instance, self.cache_name, value)

    def __delete__(self, instance):
        if hasattr(instance, self.cache_name):
            delattr(instance, self.cache_name)


def silent_reporter(res):
    """
    A generic reporter for asyncio tasks that doesn't log errors.

    For example:

    .. code-block:: python

        t = loop.create_task(coroutine())
        t.add_done_callback(hp.silent_reporter)

    This means that exceptions are *not* logged to the terminal and you won't
    get warnings about tasks not being looked at when they finish.

    This method will return True if there was no exception and None otherwise.

    It also handles and silences CancelledError.
    """
    if not res.cancelled():
        exc = res.exception()
        if not exc:
            res.result()
            return True


def reporter(res):
    """
    A generic reporter for asyncio tasks.

    For example:

    .. code-block:: python

        t = loop.create_task(coroutine())
        t.add_done_callback(hp.reporter)

    This means that exceptions are logged to the terminal and you won't
    get warnings about tasks not being looked at when they finish.

    This method will return True if there was no exception and None otherwise.

    It also handles and silences CancelledError.
    """
    if not res.cancelled():
        exc = res.exception()
        if exc:
            if not isinstance(exc, KeyboardInterrupt):
                log.exception(exc, exc_info=(type(exc), exc, exc.__traceback__))
        else:
            res.result()
            return True


def transfer_result(fut, errors_only=False):
    """
    Return a done_callback that transfers the result/errors/cancellation to fut

    If errors_only is True then it will not transfer a result to fut
    """

    def transfer(res):
        if res.cancelled():
            fut.cancel()
            return

        exc = res.exception()

        if fut.done():
            return

        if exc is not None:
            fut.set_exception(exc)
            return

        if not errors_only:
            fut.set_result(res.result())

    return transfer


def noncancelled_results_from_futs(futs):
    """
    Get back (exception, results) from a list of futures

    exception
        A single exception if all the errors are the same type
        or if there is only one exception

        otherwise it is None

    results
        A list of the results that exist
    """
    errors = set()
    results = []
    for f in futs:
        if f.done() and not f.cancelled():
            exc = f.exception()
            if exc:
                errors.add(exc)
            else:
                results.append(f.result())

    if errors:
        errors = list(errors)
        if len(errors) == 1:
            errors = errors[0]
        else:
            errors = PhotonsAppError(_errors=errors)
    else:
        errors = None

    return (errors, results)


def find_and_apply_result(final_fut, available_futs):
    """
    Find a result in available_futs with a result or exception and set that
    result/exception on both final_fut, and all the settable futs
    in available_futs.

    As a bonus, if final_fut is set, then we set that result/exception on
    available_futs.

    and if final_fut is cancelled, we cancel all the available futs

    Return True if we've changed final_fut
    """
    if final_fut.cancelled():
        for f in available_futs:
            f.cancel()
        return False

    if final_fut.done():
        current_exc = final_fut.exception()
        if current_exc:
            for f in available_futs:
                if not f.done():
                    f.set_exception(current_exc)
            return False

    errors, results = noncancelled_results_from_futs(available_futs)
    if errors:
        for f in available_futs:
            if not f.done() and not f.cancelled():
                f.set_exception(errors)
        if not final_fut.done():
            final_fut.set_exception(errors)
            return True
        return False

    if results:
        res = results[0]
        for f in available_futs:
            if not f.done() and not f.cancelled():
                f.set_result(res)
        if not final_fut.done():
            final_fut.set_result(res)
            return True
        return False

    for f in available_futs:
        if f.cancelled():
            final_fut.cancel()
            return True

    return False


class ResettableFuture(object):
    """
    A future object with a ``reset()`` function that resets it

    Usage:

    .. code-block:: python

        fut = ResettableFuture()
        fut.set_result(True)
        await fut == True

        fut.reset()
        fut.set_result(False)
        await fut == False

    This also supports an ``on_creation`` store that holds functions to be called
    when a new result is set.

    Usage:

    .. code-block:: python

        fut = ResettableFuture()
        def do_something(val):
            # Note that this callback is _not_ async
            print(val)
        fut.on_creation(do_something)
    """

    _asyncio_future_blocking = False

    def __init__(self, info=None):
        if info is None:
            self.reset()
        else:
            self.info = info
        self.creationists = []
        self.reset_fut = asyncio.Future()

    @property
    def _loop(self):
        return asyncio.get_event_loop()

    def reset(self):
        if hasattr(self, "reset_fut"):
            if not self.reset_fut.done():
                self.reset_fut.set_result(True)
        done_callbacks = getattr(self, "info", {}).get("done_callbacks", [])
        self.info = {"fut": asyncio.Future(), "done_callbacks": done_callbacks}
        for cb in done_callbacks:
            self.info["fut"].add_done_callback(cb)

    @property
    def _callbacks(self):
        return self.info["fut"]._callbacks

    def set_result(self, data):
        self.info["fut"].set_result(data)
        for func in self.creationists:
            func(data)

    def result(self):
        return self.info["fut"].result()

    def done(self):
        return self.info["fut"].done()

    def cancelled(self):
        return self.info["fut"].cancelled()

    def exception(self):
        return self.info["fut"].exception()

    def cancel(self):
        self.info["fut"].cancel()

    def ready(self):
        return self.done() and not self.cancelled()

    def settable(self):
        return not self.done() and not self.cancelled()

    def finished(self):
        return self.done() or self.cancelled()

    def set_exception(self, exc):
        self.info["fut"].set_exception(exc)

    def on_creation(self, func):
        self.creationists.append(func)

    def add_done_callback(self, func):
        self.info["done_callbacks"].append(func)
        return self.info["fut"].add_done_callback(func)

    def remove_done_callback(self, func):
        if func in self.info["done_callbacks"]:
            self.info["done_callbacks"] = [cb for cb in self.info["done_callbacks"] if cb != func]
        return self.info["fut"].remove_done_callback(func)

    def freeze(self):
        fut = ResettableFuture({k: v for k, v in self.info.items()})
        fut.creationists = list(self.creationists)
        return fut

    def __repr__(self):
        return "<ResettableFuture: {0}>".format(repr(self.info["fut"]))

    def __await__(self):
        while True:
            if self.done() or self.cancelled():
                return (yield from self.info["fut"])

            waiter = asyncio.wait(
                [self.info["fut"], self.reset_fut], return_when=asyncio.FIRST_COMPLETED
            )
            if hasattr(waiter, "__await__"):
                yield from waiter.__await__()
            else:
                yield from waiter

            if self.reset_fut.done():
                self.reset_fut = asyncio.Future()

    __iter__ = __await__


class ChildOfFuture(object):
    """
    Create a future that also considers the status of it's parent.

    So if the parent is cancelled, then this future is cancelled.
    If the parent raises an exception, then that exception is given to this result

    The special case is if the parent receives a result, then this future is
    cancelled.
    """

    _asyncio_future_blocking = False

    def __init__(self, original_fut):
        self.this_fut = asyncio.Future()
        self.original_fut = original_fut
        self.done_callbacks = []

    @property
    def _loop(self):
        return asyncio.get_event_loop()

    @property
    def _callbacks(self):
        return self.this_fut._callbacks

    def set_result(self, data):
        if self.original_fut.cancelled():
            raise InvalidStateError("CANCELLED: {!r}".format(self.original_fut))
        self.this_fut.set_result(data)

    def result(self):
        if self.original_fut.done() or self.original_fut.cancelled():
            if self.original_fut.cancelled():
                return self.original_fut.result()
            else:
                self.this_fut.cancel()
        if self.this_fut.done() or self.this_fut.cancelled():
            return self.this_fut.result()
        return self.original_fut.result()

    def done(self):
        return self.this_fut.done() or self.original_fut.done()

    def cancelled(self):
        if self.this_fut.cancelled() or self.original_fut.cancelled():
            return True

        # We cancel this_fut if original_fut gets a result
        if self.original_fut.done() and not self.original_fut.exception():
            self.this_fut.cancel()
            return True

        return False

    def exception(self):
        if self.this_fut.done() and not self.this_fut.cancelled():
            exc = self.this_fut.exception()
            if exc is not None:
                return exc

        if self.original_fut.done() and not self.original_fut.cancelled():
            exc = self.original_fut.exception()
            if exc is not None:
                return exc

        if self.this_fut.cancelled() or self.this_fut.done():
            return self.this_fut.exception()

        return self.original_fut.exception()

    def cancel_parent(self):
        if hasattr(self.original_fut, "cancel_parent"):
            self.original_fut.cancel_parent()
        else:
            self.original_fut.cancel()

    def cancel(self):
        self.this_fut.cancel()

    def ready(self):
        return self.done() and not self.cancelled()

    def settable(self):
        return not self.done() and not self.cancelled()

    def finished(self):
        return self.done() or self.cancelled()

    def set_exception(self, exc):
        self.this_fut.set_exception(exc)

    def add_done_callback(self, func):
        if func not in self.done_callbacks:
            self.done_callbacks.append(func)

        if not fut_has_callback(self.this_fut, self._done_cb):
            self.this_fut.add_done_callback(self._done_cb)
        if not fut_has_callback(self.original_fut, self._parent_done_cb):
            self.original_fut.add_done_callback(self._parent_done_cb)

    def remove_done_callback(self, func):
        if func in self.done_callbacks:
            self.done_callbacks = [cb for cb in self.done_callbacks if cb != func]
        if not self.done_callbacks:
            self.this_fut.remove_done_callback(self._done_cb)
            self.original_fut.remove_done_callback(self._parent_done_cb)

    def _done_cb(self, *args, **kwargs):
        try:
            cbs = list(self.done_callbacks)
            for cb in cbs:
                cb(*args, **kwargs)
                self.remove_done_callback(cb)
        finally:
            self.original_fut.remove_done_callback(self._parent_done_cb)

    def _parent_done_cb(self, *args, **kwargs):
        if not self.this_fut.done() and not self.this_fut.cancelled():
            self._done_cb(*args, **kwargs)

    def __repr__(self):
        return "<ChildOfFuture: {0} |:| {1}>".format(repr(self.original_fut), repr(self.this_fut))

    def __await__(self):
        while True:
            if (
                self.original_fut.done()
                and not self.original_fut.cancelled()
                and not self.original_fut.exception()
            ):
                self.this_fut.cancel()

            if self.this_fut.done():
                if hasattr(self, "waiter"):
                    del self.waiter
                return (yield from self.this_fut)

            if self.original_fut.done():
                if hasattr(self, "waiter"):
                    del self.waiter
                return (yield from self.original_fut)

            if hasattr(self, "waiter"):
                if self.waiter.cancelled() or self.waiter.done():
                    self.waiter = None

            if not getattr(self, "waiter", None):
                self.waiter = asyncio.ensure_future(
                    asyncio.wait(
                        [self.original_fut, self.this_fut], return_when=asyncio.FIRST_COMPLETED
                    )
                )

            yield from self.waiter

    __iter__ = __await__


class ThreadToAsyncQueue(object):
    """
    A Queue for requesting data from some thread:

    .. code-block:: python

        class MyQueue(ThreadToAsyncQueue):
            def create_args(self, thread_number, existing):
                '''
                This is called once when the queue is started

                and then subsequently before every request.
                '''
                if existing:
                    # Assuming you have a way of seeing if you should refresh the args
                    # Then this gives you an opportunity to do any shutdown logic for
                    # existing args and create new, or just return what exists already
                    if not should_refresh():
                        return existing

                    cleanup(existing)

                my_thread_thing = THING()
                return (my_thread_thing, )

        def onerror(exc):
            '''
            This function is passed into __init__ when you create the queue
            it is called on unexpected errors.
            the return of this function is ignored
            '''
            pass

        # If stop_fut is cancelled or has a result, then the queue will stop
        # But the thread will continue until queue.finish() is called
        queue = ThreadToAsyncQueue(stop_fut, 10, onerror)
        await queue.start()

        def action(my_thread_thing):
            '''This runs in one of the threads'''
            return my_thread_thing.stuff()

        await queue.request(action)
        await queue.finish()
    """

    def __init__(self, stop_fut, num_threads, onerror, *args, **kwargs):
        self.loop = asyncio.get_event_loop()
        self.queue = Queue()
        self.futures = {}
        self.onerror = onerror
        self.stop_fut = ChildOfFuture(stop_fut)
        self.num_threads = num_threads

        self.result_queue = asyncio.Queue()
        self.setup(*args, **kwargs)

    def setup(self, *args, **kwargs):
        """Hook for extra setup"""

    async def finish(self):
        """Signal to the tasks to stop at the next available moment"""
        self.stop_fut.cancel()
        await self.result_queue.put(None)

    def start(self, impl=None):
        """Start tasks to listen for requests made with the ``request`` method"""
        ready = []
        for thread_number, _ in enumerate(range(self.num_threads)):
            fut = asyncio.Future()
            ready.append(fut)
            thread = threading.Thread(target=self.listener, args=(thread_number, fut, impl))
            thread.start()
        async_as_background(self.set_futures())
        return asyncio.gather(*ready)

    def request(self, func):
        """Make a request and get back a future representing the result of that request"""
        key = str(uuid.uuid1())
        fut = asyncio.Future()
        self.futures[key] = fut
        self.queue.put((key, func))
        return fut

    async def set_futures(self):
        """Get results from the result_queue and set that result on the appropriate future"""
        while True:
            res = await self.result_queue.get()
            if self.stop_fut.finished():
                break

            if not res:
                continue

            if isinstance(res, tuple) and len(res) == 3:
                key, result, exception = res
            else:
                error = PhotonsAppError("Unknown item on queue", got=res)
                self.onerror(error)
                continue

            try:
                self.find_and_set_future(key, result, exception)
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                raise
            except:
                exc_info = sys.exc_info()
                self.onerror(exc_info)
                log.error(exc_info[1], exc_info=exc_info)

    def find_and_set_future(self, key, result, exception):
        """Find and set future for this key to provided result or exception"""
        if key in self.futures:
            fut = self.futures.pop(key)
            if not fut.done() and not fut.cancelled():
                if result is Nope:
                    fut.set_exception(exception)
                else:
                    fut.set_result(result)

    def process(self, key, proc):
        """Process a request"""
        result = Nope
        exception = Nope
        try:
            result = proc()
        except Exception as error:
            exception = error
            self.onerror(sys.exc_info())

        try:
            self.loop.call_soon_threadsafe(self.result_queue.put_nowait, (key, result, exception))
        except RuntimeError:
            log.error(
                PhotonsAppError(
                    "Failed to put result onto the loop because it was closed",
                    key=key,
                    result=result,
                    exception=exception,
                )
            )

    def listener(self, thread_number, ready_fut, impl=None):
        """Start the thread!"""
        args = self.create_args(thread_number, existing=None)
        self.loop.call_soon_threadsafe(ready_fut.set_result, True)
        self._listener(thread_number, impl, args)

    def create_args(self, thread_number, existing):
        """
        Hook to return extra args to give to functions when the are requested

        This is called once when the queue is started

        and then subsequently before every request.

        It must return None or a tuple of arguments to pass into request functions
        """

    def _listener(self, thread_number, impl, args):
        """Forever, with error catching, get nxt request of the queue and process"""
        while True:
            if self.stop_fut.finished():
                break

            try:
                nxt = self.queue.get(timeout=0.05)
            except Empty:
                continue
            else:
                if self.stop_fut.finished():
                    break

                try:
                    args = self.create_args(thread_number, existing=args)
                    if args is None:
                        args = ()

                    (impl or self.listener_impl)(nxt, *args)
                except KeyboardInterrupt:
                    raise
                except:
                    exc_info = sys.exc_info()
                    log.error(exc_info[1], exc_info=exc_info)
                    self.onerror(exc_info)

    def wrap_request(self, proc, args):
        """Return a function that will perform the work"""

        def wrapped():
            return proc(*args)

        return wrapped

    def listener_impl(self, nxt, *args):
        """Just call out to process"""
        if isinstance(nxt, tuple) and len(nxt) == 2:
            key, proc = nxt
            self.process(key, wraps(proc)(self.wrap_request(proc, args)))
        else:
            error = PhotonsAppError("Unknown item in the queue", got=nxt)
            self.onerror(error)
            log.error(error)
