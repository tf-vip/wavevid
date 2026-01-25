"""Classic horizontal waveform visualizer."""
from PIL import Image, ImageDraw
import numpy as np
from .base import BaseVisualizer


class WaveformVisualizer(BaseVisualizer):
    """Horizontal amplitude waveform visualization."""

    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render waveform for current frame."""
        img = background.copy()
        draw = ImageDraw.Draw(img)

        waveform = frame_data['waveform'][frame_idx]
        amplitude = frame_data['amplitude'][frame_idx]

        # Scale waveform by current amplitude for reactivity
        scale = 0.3 + amplitude * 0.7

        center_y = self.height // 2
        max_height = self.height * 0.4

        n_points = len(waveform)
        points = []

        for i, val in enumerate(waveform):
            x = int(i * self.width / n_points)
            y = int(center_y + val * max_height * scale)
            points.append((x, y))

        # Draw waveform line
        if len(points) > 1:
            draw.line(points, fill=self.wave_color, width=3)

        # Draw mirror reflection (optional aesthetic)
        mirror_points = [(p[0], 2 * center_y - p[1]) for p in points]
        if len(mirror_points) > 1:
            # Slightly dimmer for reflection
            dim_color = tuple(int(c * 0.5) for c in self.wave_color)
            draw.line(mirror_points, fill=dim_color, width=2)

        return img
