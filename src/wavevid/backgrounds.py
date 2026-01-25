"""Background generators."""
from PIL import Image
import numpy as np


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def create_solid_background(width: int, height: int, color: str) -> Image.Image:
    """Create solid color background."""
    rgb = hex_to_rgb(color)
    return Image.new('RGB', (width, height), rgb)


def create_gradient_background(width: int, height: int, colors: str) -> Image.Image:
    """Create vertical gradient background from two colors."""
    color1, color2 = colors.split(',')
    rgb1 = hex_to_rgb(color1.strip())
    rgb2 = hex_to_rgb(color2.strip())

    img = Image.new('RGB', (width, height))
    pixels = img.load()

    for y in range(height):
        ratio = y / height
        r = int(rgb1[0] * (1 - ratio) + rgb2[0] * ratio)
        g = int(rgb1[1] * (1 - ratio) + rgb2[1] * ratio)
        b = int(rgb1[2] * (1 - ratio) + rgb2[2] * ratio)
        for x in range(width):
            pixels[x, y] = (r, g, b)

    return img


def create_image_background(width: int, height: int, path: str) -> Image.Image:
    """Load and resize image as background."""
    img = Image.open(path).convert('RGB')
    return img.resize((width, height), Image.Resampling.LANCZOS)


def get_background(width: int, height: int, bg_type: str, bg_value: str) -> Image.Image:
    """Get background image based on type."""
    if bg_type == 'gradient':
        return create_gradient_background(width, height, bg_value)
    elif bg_type == 'image':
        return create_image_background(width, height, bg_value)
    else:  # color (default)
        return create_solid_background(width, height, bg_value)
