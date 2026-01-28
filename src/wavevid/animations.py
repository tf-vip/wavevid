"""Modular animation system for wavevid elements."""
from dataclasses import dataclass
from typing import Callable
import math


@dataclass
class AnimationState:
    """State passed to drawing functions."""
    opacity: float = 1.0      # 0.0 to 1.0
    scale: float = 1.0        # 1.0 = normal size
    offset_x: float = 0.0     # pixels
    offset_y: float = 0.0     # pixels
    rotation: float = 0.0     # degrees
    blur: float = 0.0         # blur radius
    visible_chars: int = -1   # -1 = all, for typewriter effect

    def merge(self, other: 'AnimationState') -> 'AnimationState':
        """Combine two states (multiply opacity/scale, add offsets)."""
        return AnimationState(
            opacity=self.opacity * other.opacity,
            scale=self.scale * other.scale,
            offset_x=self.offset_x + other.offset_x,
            offset_y=self.offset_y + other.offset_y,
            rotation=self.rotation + other.rotation,
            blur=max(self.blur, other.blur),
            visible_chars=min(self.visible_chars, other.visible_chars) if self.visible_chars >= 0 and other.visible_chars >= 0 else max(self.visible_chars, other.visible_chars)
        )


# Easing functions
def ease_linear(t: float) -> float:
    return t

def ease_in_quad(t: float) -> float:
    return t * t

def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) * (1 - t)

def ease_in_out_quad(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2

def ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)

def ease_out_back(t: float) -> float:
    """Slight overshoot then settle."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

def ease_out_elastic(t: float) -> float:
    """Bouncy effect."""
    if t == 0 or t == 1:
        return t
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


EASINGS = {
    'linear': ease_linear,
    'in_quad': ease_in_quad,
    'out_quad': ease_out_quad,
    'in_out_quad': ease_in_out_quad,
    'out_cubic': ease_out_cubic,
    'out_back': ease_out_back,
    'out_elastic': ease_out_elastic,
}


class Animation:
    """Base animation class."""

    def __init__(self, duration: float, delay: float = 0.0, easing: str = 'out_quad'):
        self.duration = duration
        self.delay = delay
        self.easing_fn = EASINGS.get(easing, ease_out_quad)

    def get_state(self, time: float, fps: int) -> AnimationState:
        """Get animation state at given time (seconds)."""
        if time < self.delay:
            return self._get_start_state()

        elapsed = time - self.delay
        if elapsed >= self.duration:
            return self._get_end_state()

        progress = self.easing_fn(elapsed / self.duration)
        return self._interpolate(progress)

    def _get_start_state(self) -> AnimationState:
        return AnimationState()

    def _get_end_state(self) -> AnimationState:
        return AnimationState()

    def _interpolate(self, progress: float) -> AnimationState:
        return AnimationState()

    def total_duration(self) -> float:
        return self.delay + self.duration


class FadeIn(Animation):
    """Fade from transparent to opaque."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0, easing: str = 'out_quad'):
        super().__init__(duration, delay, easing)

    def _get_start_state(self) -> AnimationState:
        return AnimationState(opacity=0.0)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(opacity=1.0)

    def _interpolate(self, progress: float) -> AnimationState:
        return AnimationState(opacity=progress)


class FadeOut(Animation):
    """Fade from opaque to transparent."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0, easing: str = 'in_quad'):
        super().__init__(duration, delay, easing)

    def _get_start_state(self) -> AnimationState:
        return AnimationState(opacity=1.0)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(opacity=0.0)

    def _interpolate(self, progress: float) -> AnimationState:
        return AnimationState(opacity=1.0 - progress)


class ScaleDown(Animation):
    """Scale from larger to normal size."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0,
                 start_scale: float = 1.1, end_scale: float = 1.0, easing: str = 'out_quad'):
        super().__init__(duration, delay, easing)
        self.start_scale = start_scale
        self.end_scale = end_scale

    def _get_start_state(self) -> AnimationState:
        return AnimationState(scale=self.start_scale)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(scale=self.end_scale)

    def _interpolate(self, progress: float) -> AnimationState:
        scale = self.start_scale + (self.end_scale - self.start_scale) * progress
        return AnimationState(scale=scale)


class ScaleUp(Animation):
    """Scale from smaller to normal size."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0,
                 start_scale: float = 0.8, end_scale: float = 1.0, easing: str = 'out_back'):
        super().__init__(duration, delay, easing)
        self.start_scale = start_scale
        self.end_scale = end_scale

    def _get_start_state(self) -> AnimationState:
        return AnimationState(scale=self.start_scale)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(scale=self.end_scale)

    def _interpolate(self, progress: float) -> AnimationState:
        scale = self.start_scale + (self.end_scale - self.start_scale) * progress
        return AnimationState(scale=scale)


class SlideUp(Animation):
    """Slide from below into position."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0,
                 distance: float = 50, easing: str = 'out_cubic'):
        super().__init__(duration, delay, easing)
        self.distance = distance

    def _get_start_state(self) -> AnimationState:
        return AnimationState(offset_y=self.distance)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(offset_y=0)

    def _interpolate(self, progress: float) -> AnimationState:
        return AnimationState(offset_y=self.distance * (1 - progress))


class SlideDown(Animation):
    """Slide from above into position."""

    def __init__(self, duration: float = 0.5, delay: float = 0.0,
                 distance: float = 50, easing: str = 'out_cubic'):
        super().__init__(duration, delay, easing)
        self.distance = distance

    def _get_start_state(self) -> AnimationState:
        return AnimationState(offset_y=-self.distance)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(offset_y=0)

    def _interpolate(self, progress: float) -> AnimationState:
        return AnimationState(offset_y=-self.distance * (1 - progress))


class Typewriter(Animation):
    """Reveal characters one by one."""

    def __init__(self, duration: float = 1.0, delay: float = 0.0,
                 total_chars: int = 0, easing: str = 'linear'):
        super().__init__(duration, delay, easing)
        self.total_chars = total_chars

    def _get_start_state(self) -> AnimationState:
        return AnimationState(visible_chars=0)

    def _get_end_state(self) -> AnimationState:
        return AnimationState(visible_chars=self.total_chars)

    def _interpolate(self, progress: float) -> AnimationState:
        chars = int(self.total_chars * progress)
        return AnimationState(visible_chars=chars)


class Parallel(Animation):
    """Run multiple animations simultaneously."""

    def __init__(self, *animations: Animation):
        self.animations = animations
        max_duration = max(a.total_duration() for a in animations) if animations else 0
        super().__init__(max_duration, 0, 'linear')

    def get_state(self, time: float, fps: int) -> AnimationState:
        state = AnimationState()
        for anim in self.animations:
            state = state.merge(anim.get_state(time, fps))
        return state

    def total_duration(self) -> float:
        return max(a.total_duration() for a in self.animations) if self.animations else 0


class Sequential(Animation):
    """Run animations one after another."""

    def __init__(self, *animations: Animation):
        self.animations = animations
        total = sum(a.total_duration() for a in animations)
        super().__init__(total, 0, 'linear')

    def get_state(self, time: float, fps: int) -> AnimationState:
        elapsed = 0
        for anim in self.animations:
            anim_duration = anim.total_duration()
            if time < elapsed + anim_duration:
                return anim.get_state(time - elapsed, fps)
            elapsed += anim_duration
        # Return final state of last animation
        if self.animations:
            return self.animations[-1]._get_end_state()
        return AnimationState()

    def total_duration(self) -> float:
        return sum(a.total_duration() for a in self.animations)


class Delay(Animation):
    """Wait before continuing (use in Sequential)."""

    def __init__(self, duration: float):
        super().__init__(duration, 0, 'linear')

    def get_state(self, time: float, fps: int) -> AnimationState:
        return AnimationState()


class NoAnimation(Animation):
    """No animation - static state."""

    def __init__(self):
        super().__init__(0, 0, 'linear')

    def get_state(self, time: float, fps: int) -> AnimationState:
        return AnimationState()


# Preset animation combinations
def intro_title_animation(title_duration: float = 1.0, subtitle_delay: float = 0.5,
                          subtitle_duration: float = 0.5) -> dict:
    """Standard intro animation: fade+scale title, then fade subtitle."""
    return {
        'title': Parallel(
            FadeIn(duration=title_duration, easing='out_quad'),
            ScaleDown(duration=title_duration, start_scale=1.15, easing='out_cubic')
        ),
        'subtitle': FadeIn(duration=subtitle_duration, delay=title_duration + subtitle_delay, easing='out_quad')
    }


def avatar_pulse_animation(duration: float = 2.0) -> Animation:
    """Subtle pulse effect for avatar."""
    return Parallel(
        FadeIn(duration=0.5),
        ScaleUp(duration=duration, start_scale=0.9, end_scale=1.0, easing='out_elastic')
    )


def slide_fade_animation(duration: float = 0.5, delay: float = 0.0,
                         direction: str = 'up') -> Animation:
    """Slide + fade combination."""
    slide_cls = SlideUp if direction == 'up' else SlideDown
    return Parallel(
        FadeIn(duration=duration, delay=delay),
        slide_cls(duration=duration, delay=delay)
    )
