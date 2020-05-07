from photons_canvas.animations import register, AnimationRunner

from photons_app.actions import an_action

from delfick_project.option_merge import MergedOptions
from delfick_project.norms import sb

import logging

log = logging.getLogger("photons_canvas.animations.addon")


@an_action(needs_target=True)
async def animate(collector, target, reference, artifact, **kwargs):
    available = [n.split(":", 1)[1] for n in register.available_animations()]

    if (
        reference in available
        or reference.startswith("transition:")
        or reference.startswith("feature:")
    ):
        ref = artifact
        artifact = reference
        reference = ref

    run_options = collector.photons_app.extra_as_json
    reference = collector.reference_object(reference)

    options = run_options
    if isinstance(run_options, list):
        run_options = {"animations": run_options}

    if artifact not in (None, "", sb.NotSpecified):
        options = sb.NotSpecified
        background = sb.NotSpecified

        if "options" in run_options:
            options = run_options.pop("options")

        if "background" in run_options:
            background = run_options.pop("background")

        layered = {"animations": [[artifact, background, options]], "animation_limit": 1}
        run_options = MergedOptions.using(run_options, layered).as_dict()

    def errors(e):
        log.error(e)

    conf = collector.configuration
    photons_app = conf["photons_app"]

    with photons_app.using_graceful_future() as final_future:
        async with target.session() as sender:
            runner = AnimationRunner(
                sender,
                reference,
                run_options,
                final_future=final_future,
                error_catcher=errors,
                message_timeout=1,
                animation_options=conf.get("animation_options", {}),
            )
            await runner.run()
