"""Spectrum FFT analyzer visualizer with peak hold."""
from PIL import Image, ImageDraw
import numpy as np
from .base import BaseVisualizer


class SpectrumVisualizer(BaseVisualizer):
    """FFT spectrum analyzer with gradient bars and peak indicators."""

    def __init__(self, width: int, height: int, wave_color: str, **kwargs):
        super().__init__(width, height, wave_color)
        self.peak_values = None
        self.peak_decay = 0.95  # Peak decay rate per frame

    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render spectrum analyzer for current frame."""
        img = background.copy()
        draw = ImageDraw.Draw(img)

        bands = frame_data['bands'][frame_idx]
        amplitude = frame_data['amplitude'][frame_idx]

        # Initialize peaks on first frame
        if self.peak_values is None:
            self.peak_values = np.zeros(len(bands))

        n_bars = len(bands)
        bar_width = self.width / n_bars * 0.85
        gap = self.width / n_bars * 0.15

        max_height = self.height * 0.7
        base_y = self.height * 0.85

        # Update peaks
        for i, val in enumerate(bands):
            bar_value = val * (0.6 + amplitude * 0.4)
            if bar_value > self.peak_values[i]:
                self.peak_values[i] = bar_value
            else:
                self.peak_values[i] *= self.peak_decay

        for i, val in enumerate(bands):
            x = i * (bar_width + gap) + gap / 2
            bar_value = val * (0.6 + amplitude * 0.4)
            bar_height = bar_value * max_height

            # Gradient color based on frequency position (low=base color, high=brighter)
            freq_ratio = i / n_bars
            # Shift hue from base color toward cyan/white at higher frequencies
            r = int(self.wave_color[0] * (1.0 - freq_ratio * 0.3))
            g = int(self.wave_color[1] * (0.7 + freq_ratio * 0.3))
            b = int(self.wave_color[2] * (0.7 + freq_ratio * 0.3))
            color = (min(255, r), min(255, g), min(255, b))

            # Draw bar with rounded top
            if bar_height > 2:
                # Main bar
                draw.rectangle([
                    x, base_y - bar_height,
                    x + bar_width, base_y
                ], fill=color)

                # Glow effect (slightly wider, dimmer)
                glow_color = tuple(int(c * 0.3) for c in color)
                draw.rectangle([
                    x - 1, base_y - bar_height - 2,
                    x + bar_width + 1, base_y - bar_height
                ], fill=glow_color)

            # Draw peak indicator
            peak_y = base_y - self.peak_values[i] * max_height
            peak_color = (255, 255, 255)  # White peak indicator
            draw.rectangle([
                x, peak_y - 3,
                x + bar_width, peak_y
            ], fill=peak_color)

            # Draw subtle reflection
            reflection_height = bar_height * 0.2
            dim_color = tuple(int(c * 0.15) for c in color)
            draw.rectangle([
                x, base_y,
                x + bar_width, base_y + reflection_height
            ], fill=dim_color)

        return img
