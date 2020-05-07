from photons_app.errors import PhotonsAppError

from delfick_project.norms import Meta, sb
import enum


class AnimationType(enum.Enum):
    FEATURE = "feature"
    TRANSITION = "transition"


class NoSuchAnimation(PhotonsAppError):
    desc = "Couldn't find specified animation"


class NoSuchAnimationType(PhotonsAppError):
    desc = "Not a valid animation type"


animations = {AnimationType.FEATURE: {}, AnimationType.TRANSITION: {}}


def available_animations():
    result = []
    for t, ans in animations.items():
        for name in ans:
            result.append(f"{t.value}:{name}")
    return sorted(result)


class Animator:
    def __init__(self, Animation, Options, *, name=None, typ=AnimationType.FEATURE):
        if name is None:
            count = sum([len(a) for a in animations.values()])
            name = f"animation_{count+1}"

        self.typ = typ
        self.name = name
        self.Options = Options
        self.Animation = Animation

    def clone(self, *, name=None, typ=None):
        clone = Animator(self.Animation, self.Options, name=self.name, typ=self.typ)
        if name is not None:
            clone.name = name
        if typ is not None:
            clone.typ = typ
        return clone

    def resolver(self, options=None, background=None):
        if options is None:
            options = {}

        background = (
            background if background in (True, False) else background in (sb.NotSpecified, None)
        )

        return self.Resolver(self, options, background)

    class Resolver:
        def __init__(self, animator, options, background):
            self.options = options
            self.animator = animator
            self.background = background

        def resolve(self):
            def make_animation():
                options = self.animator.Options.FieldSpec().normalise(Meta.empty(), self.options)
                animation = self.animator.Animation(options)
                if self.options is not sb.NotSpecified:
                    for attr in animation.overridable:
                        if attr in self.options:
                            setattr(animation, attr, self.options[attr])
                return animation

            # Make sure the options can be resolved
            make_animation()

            return self.animator.typ, make_animation, self.background


class an_animation:
    def __init__(self, name, Options, transition=False):
        self.name = name
        self.Options = Options
        self.transition = transition

    def __call__(self, Animation):
        self.Animation = Animation

        typ = AnimationType.TRANSITION if self.transition else AnimationType.FEATURE
        animations[typ][self.name] = Animator(Animation, self.Options, name=self.name, typ=typ)
        return Animation


def resolve(name):
    if isinstance(name, tuple):
        return Animator(*name)

    typ = None
    if ":" in name:
        typ, name = name.split(":", 1)

    features = animations[AnimationType.FEATURE]
    transitions = animations[AnimationType.TRANSITION]

    if name not in features and name not in transitions:
        raise NoSuchAnimation(wanted=name, available=available_animations())

    animator = features[name] if name in features else transitions[name]

    if typ is not None:
        types = {a.value: a for a in AnimationType}
        if typ not in types:
            raise NoSuchAnimationType(want=typ, available=sorted(types))
        animator = animator.clone(typ=types[typ])

    return animator
