"""Circular radial visualizer."""
from PIL import Image, ImageDraw
import numpy as np
from .base import BaseVisualizer


class RadialVisualizer(BaseVisualizer):
    """Circular bars pulsing from center."""

    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render radial visualization for current frame."""
        img = background.copy()
        draw = ImageDraw.Draw(img)

        bands = frame_data['bands'][frame_idx]
        amplitude = frame_data['amplitude'][frame_idx]

        center_x = self.width // 2
        center_y = self.height // 2

        base_radius = min(self.width, self.height) * 0.15
        max_bar_length = min(self.width, self.height) * 0.3

        n_bars = len(bands)

        for i, val in enumerate(bands):
            angle = (2 * np.pi * i / n_bars) - np.pi / 2

            # Bar length based on frequency band value
            bar_length = val * max_bar_length * (0.5 + amplitude * 0.5)

            # Start and end points
            x1 = center_x + np.cos(angle) * base_radius
            y1 = center_y + np.sin(angle) * base_radius
            x2 = center_x + np.cos(angle) * (base_radius + bar_length)
            y2 = center_y + np.sin(angle) * (base_radius + bar_length)

            # Color gradient based on position
            hue_shift = i / n_bars
            r = int(self.wave_color[0] * (1 - hue_shift * 0.3))
            g = int(self.wave_color[1] * (0.7 + hue_shift * 0.3))
            b = int(self.wave_color[2] * (0.7 + hue_shift * 0.3))
            color = (min(255, r), min(255, g), min(255, b))

            draw.line([(x1, y1), (x2, y2)], fill=color, width=4)

        # Draw center circle
        circle_radius = base_radius * (0.8 + amplitude * 0.2)
        draw.ellipse([
            center_x - circle_radius, center_y - circle_radius,
            center_x + circle_radius, center_y + circle_radius
        ], outline=self.wave_color, width=2)

        return img
