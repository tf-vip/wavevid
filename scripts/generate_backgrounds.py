#!/usr/bin/env python3
"""Generate royalty-free gradient backgrounds for wavevid."""
from PIL import Image, ImageDraw
import math
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "src/wavevid/backgrounds"
WIDTH, HEIGHT = 1920, 1080

GRADIENTS = [
    # (name, colors, style)
    ("bg1", ["#1a1a2e", "#16213e", "#0f3460"], "vertical"),      # Deep blue
    ("bg2", ["#0f0c29", "#302b63", "#24243e"], "diagonal"),      # Purple night
    ("bg3", ["#232526", "#414345"], "vertical"),                  # Dark gray
    ("bg4", ["#000000", "#434343"], "radial"),                    # Black radial
    ("bg5", ["#1e3c72", "#2a5298"], "vertical"),                  # Ocean blue
    ("bg6", ["#141e30", "#243b55"], "diagonal"),                  # Midnight
    ("bg7", ["#0f2027", "#203a43", "#2c5364"], "vertical"),      # Teal dark
    ("bg8", ["#200122", "#6f0000"], "diagonal"),                  # Dark red
    ("bg9", ["#1f1c2c", "#928dab"], "vertical"),                  # Lavender mist
    ("bg10", ["#0a0a0a", "#1a1a2e"], "radial"),                   # Deep black
]


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def interpolate_color(color1: tuple, color2: tuple, t: float) -> tuple:
    return tuple(int(c1 + (c2 - c1) * t) for c1, c2 in zip(color1, color2))


def create_vertical_gradient(colors: list[str]) -> Image.Image:
    img = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    rgb_colors = [hex_to_rgb(c) for c in colors]

    segments = len(rgb_colors) - 1
    segment_height = HEIGHT / segments

    for y in range(HEIGHT):
        segment = min(int(y / segment_height), segments - 1)
        t = (y - segment * segment_height) / segment_height
        color = interpolate_color(rgb_colors[segment], rgb_colors[segment + 1], t)
        draw.line([(0, y), (WIDTH, y)], fill=color)

    return img


def create_diagonal_gradient(colors: list[str]) -> Image.Image:
    img = Image.new('RGB', (WIDTH, HEIGHT))
    rgb_colors = [hex_to_rgb(c) for c in colors]

    if len(rgb_colors) == 2:
        c1, c2 = rgb_colors
    else:
        c1, c2 = rgb_colors[0], rgb_colors[-1]

    max_dist = WIDTH + HEIGHT

    for y in range(HEIGHT):
        for x in range(WIDTH):
            t = (x + y) / max_dist
            color = interpolate_color(c1, c2, t)
            img.putpixel((x, y), color)

    return img


def create_radial_gradient(colors: list[str]) -> Image.Image:
    img = Image.new('RGB', (WIDTH, HEIGHT))
    rgb_colors = [hex_to_rgb(c) for c in colors]

    if len(rgb_colors) == 2:
        inner, outer = rgb_colors
    else:
        inner, outer = rgb_colors[-1], rgb_colors[0]

    cx, cy = WIDTH // 2, HEIGHT // 2
    max_dist = math.sqrt(cx**2 + cy**2)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            t = min(dist / max_dist, 1.0)
            color = interpolate_color(inner, outer, t)
            img.putpixel((x, y), color)

    return img


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, colors, style in GRADIENTS:
        print(f"Generating {name} ({style})...")

        if style == "vertical":
            img = create_vertical_gradient(colors)
        elif style == "diagonal":
            img = create_diagonal_gradient(colors)
        elif style == "radial":
            img = create_radial_gradient(colors)
        else:
            img = create_vertical_gradient(colors)

        output_path = OUTPUT_DIR / f"{name}.jpg"
        img.save(output_path, "JPEG", quality=90)
        print(f"  Saved: {output_path}")

    print(f"\nGenerated {len(GRADIENTS)} backgrounds in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
