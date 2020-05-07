from photons_canvas.animations import options

from photons_protocol.types import enum_spec

from delfick_project.norms import dictobj, sb
import enum


class MarqueeDirection(enum.Enum):
    LEFT = "left"
    RIGHT = "right"


class Options(dictobj.Spec):
    text_color = dictobj.Field(options.ColorOption(50, 1, 0.5, 3500))
    text = dictobj.Field(sb.string_spec, default="LIFX is awesome!")
    num_iterations = dictobj.Field(sb.integer_spec, default=-1)
    large_font = dictobj.Field(sb.boolean, default=False)
    speed = dictobj.Field(sb.integer_spec, default=1)
    direction = dictobj.Field(
        enum_spec(None, MarqueeDirection, unpacking=True), default=MarqueeDirection.LEFT
    )

    def final_iteration(self, iteration):
        if self.num_iterations == -1:
            return False
        return self.num_iterations <= iteration
