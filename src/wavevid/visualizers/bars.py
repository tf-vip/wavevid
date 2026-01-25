"""Vertical equalizer bars visualizer."""
from PIL import Image, ImageDraw
import numpy as np
from .base import BaseVisualizer


class BarsVisualizer(BaseVisualizer):
    """Vertical equalizer-style frequency bars."""

    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render bar visualization for current frame."""
        img = background.copy()
        draw = ImageDraw.Draw(img)

        bands = frame_data['bands'][frame_idx]
        amplitude = frame_data['amplitude'][frame_idx]

        n_bars = len(bands)
        bar_width = self.width / n_bars * 0.8
        gap = self.width / n_bars * 0.2

        max_height = self.height * 0.6
        base_y = self.height * 0.8

        for i, val in enumerate(bands):
            x = i * (bar_width + gap) + gap / 2

            # Bar height based on frequency band value
            bar_height = val * max_height * (0.5 + amplitude * 0.5)

            # Gradient color from bottom to top
            intensity = val
            r = int(self.wave_color[0] * (0.5 + intensity * 0.5))
            g = int(self.wave_color[1] * (0.5 + intensity * 0.5))
            b = int(self.wave_color[2] * (0.5 + intensity * 0.5))
            color = (min(255, r), min(255, g), min(255, b))

            # Draw bar
            draw.rectangle([
                x, base_y - bar_height,
                x + bar_width, base_y
            ], fill=color)

            # Draw reflection (dimmer)
            reflection_height = bar_height * 0.3
            dim_color = tuple(int(c * 0.3) for c in color)
            draw.rectangle([
                x, base_y,
                x + bar_width, base_y + reflection_height
            ], fill=dim_color)

        return img
