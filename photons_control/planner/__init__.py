"""
The planner is a mechanism for gathering information from many devices and
receive that information as we get it. This handles getting multiple pieces of
information, information that depends on other information, and also handles
getting information to you as it's received without having to wait for slower
devices.

Usage is via the Gatherer class:

.. code-block:: python

    async with target.session() as sender:
        plans = sender.make_plans("power", "label")

        # sender.gatherer is just a Gatherer(sender) that is cached on the sender
        async for serial, label, info in sender.gatherer.gather(reference):
            ...

.. autoclass:: photons_control.planner.gatherer.Gatherer

.. autofunction:: photons_control.planner.plans.make_plans

Plans
-----

The gatherer is just a mechanism that executes plans. There are default plans
that are registered with default names, and you may use those labels as positional
arguments to the make_plans function to get a plans dictionary with those plans.

Or you may create your own plans by subclassing the Plan class.

For example:

.. code-block:: python

    # Using a_plan decorator is optional, and is just for registering a name
    # for this plan
    @a_plan("uptime")
    class UptimePlan(Plan):
        messages = [DeviceMessages.GetInfo()]

        class Instance(Plan.Instance):
            def process(self, pkt):
                # This method gets all replies from the device, not just
                # replies to the messages sent by this plan
                if pkt | DeviceMessages.StateInfo:
                    self.uptime = pkt.uptime
                    # We have information, tell the planner to use info() to get
                    # the final result from this plan
                    return True

            async def info(self):
                return self.uptime

    # We've used a_plan, so we can either use this plan by name like:
    plans = make_plans("uptime")
    async for serial, label, info in g.gather(plans, reference):
        ....

    # Or we can use the plan directly
    plans = make_plans(uptime=UptimePlan())
    async for serial, label, info in g.gather(plans, reference):
        ...

.. autoclass:: photons_control.planner.plans.Plan

.. autoclass:: photons_control.planner.plans.Skip

.. autoclass:: photons_control.planner.plans.NoMessages

.. autoclass:: photons_control.planner.plans.PacketPlan
"""
from photons_control.planner.plans import Skip, NoMessages, Plan, PacketPlan, a_plan, make_plans
from photons_control.planner.gatherer import Gatherer

__all__ = ["Skip", "NoMessages", "Plan", "PacketPlan", "a_plan", "make_plans", "Gatherer"]
