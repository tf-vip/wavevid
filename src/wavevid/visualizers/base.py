"""Base visualizer class."""
from abc import ABC, abstractmethod
from PIL import Image
import numpy as np


class BaseVisualizer(ABC):
    """Abstract base class for visualizers."""

    def __init__(self, width: int, height: int, wave_color: str):
        self.width = width
        self.height = height
        self.wave_color = self._hex_to_rgb(wave_color)

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @abstractmethod
    def render_frame(self, background: Image.Image, frame_data: dict, frame_idx: int) -> Image.Image:
        """Render a single frame with visualization overlay."""
        pass
