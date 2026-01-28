"""Reactive particle system visualizer."""
from PIL import Image, ImageDraw
import numpy as np
import math
from .base import BaseVisualizer


class ParticlesVisualizer(BaseVisualizer):
    """Particles orbiting center, pulsing with audio amplitude."""

    def __init__(self, width: int, height: int, wave_color: str, **kwargs):
        super().__init__(width, height, wave_color)
        self.n_particles = 200
        self.particles = self._init_particles()

    def _init_particles(self):
        """Initialize particles with random positions and velocities."""
        particles = []
        for i in range(self.n_particles):
            # Random angle and distance from center
            angle = np.random.uniform(0, 2 * math.pi)
            base_radius = np.random.uniform(0.15, 0.4) * min(self.width, self.height)
            # Angular velocity for orbit
            angular_vel = np.random.uniform(0.005, 0.02) * (1 if np.random.random() > 0.5 else -1)
            # Size
            size = np.random.uniform(2, 6)
            # Frequency band assignment (0-63 mapped to particle index)
            band_idx = int((i / self.n_particles) * 64)

            particles.append({
                'angle': angle,
                'base_radius': base_radius,
                'angular_vel': angular_vel,
                'size': size,
                'band_idx': band_idx,
            })
        return particles

    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render particle system for current frame."""
        img = background.copy()
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Create overlay for particles with alpha
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        bands = frame_data['bands'][frame_idx]
        amplitude = frame_data['amplitude'][frame_idx]

        cx, cy = self.width // 2, self.height // 2

        for p in self.particles:
            # Update angle for orbit
            p['angle'] += p['angular_vel']

            # Get band value for this particle
            band_val = bands[min(p['band_idx'], len(bands) - 1)]

            # Radius pulses with amplitude and band value
            pulse = 1.0 + amplitude * 0.5 + band_val * 0.3
            radius = p['base_radius'] * pulse

            # Calculate position
            x = cx + radius * math.cos(p['angle'])
            y = cy + radius * math.sin(p['angle'])

            # Size pulses with band
            size = p['size'] * (1 + band_val * 0.5)

            # Color based on band (gradient from base color to complementary)
            band_ratio = p['band_idx'] / 64
            r = int(self.wave_color[0] * (1 - band_ratio * 0.5) + 255 * band_ratio * 0.5)
            g = int(self.wave_color[1] * (1 - band_ratio * 0.3))
            b = int(self.wave_color[2] * (1 - band_ratio * 0.2) + 100 * band_ratio)

            # Alpha based on amplitude
            alpha = int(150 + amplitude * 100)
            color = (min(255, r), min(255, g), min(255, b), min(255, alpha))

            # Draw particle as ellipse
            draw.ellipse([
                x - size, y - size,
                x + size, y + size
            ], fill=color)

            # Draw glow for brighter particles
            if band_val > 0.5:
                glow_size = size * 2
                glow_alpha = int(50 * band_val)
                glow_color = (min(255, r), min(255, g), min(255, b), glow_alpha)
                draw.ellipse([
                    x - glow_size, y - glow_size,
                    x + glow_size, y + glow_size
                ], fill=glow_color)

        # Composite overlay onto image
        img = Image.alpha_composite(img, overlay)
        return img
