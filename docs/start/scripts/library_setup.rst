.. _library_setup:

Using the ``library_setup`` function
====================================

To integrate Photons with an existing script or to control command-line options,
use the ``library_setup`` function to instantiate Photons.

For example:

.. code-block:: python

    from photons_app.executor import library_setup

    from photons_messages import DeviceMessages

    import asyncio


    async def get_label(collector):
        lan_target = collector.resolve_target("lan")
        reference = collector.reference_object("_")

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")


    if __name__ == "__main__":
        loop = asyncio.new_event_loop()
        collector = library_setup()
        try:
            loop.run_until_complete(get_label(collector))
        finally:
            loop.run_until_complete(collector.stop_photons_app())
            loop.close()

If the script only performs Photons tasks, use the collector to create the
asyncio event loop and perform cleanup functions:

.. code-block:: python

    from photons_app.executor import library_setup
    from photons_messages import DeviceMessages

    async def get_label(collector):
        lan_target = collector.resolve_target("lan")
        reference = collector.reference_object("_")

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")

    if __name__ == "__main__":
        collector = library_setup()
        collector.run_coro_as_main(get_label(collector))

Use ``argparse`` to parse command-line arguments:

.. code-block:: python

    from photons_app.executor import library_setup
    from photons_messages import DeviceMessages

    import argparse

    async def get_label(collector):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--target", choices=[collector.configuration["target_register"].targets.keys()]
        )
        parser.add_argument("--reference", default="_")
        args = parser.parse_args()

        lan_target = collector.resolve_target(args.target)
        reference = collector.reference_object(args.reference)

        async for pkt in lan_target.send(DeviceMessages.GetLabel(), reference):
            print(f"{pkt.serial}: {pkt.label}")

    if __name__ == "__main__":
        collector = library_setup()
        collector.run_coro_as_main(get_label(collector))

.. note:: ``run_coro_as_main`` is similar to the
    `asyncio.run <https://docs.python.org/3/library/asyncio-task.html#asyncio.run>`_
    function in the Python standard library but does extra work to ensure the event loop
    is shut down cleanly.
