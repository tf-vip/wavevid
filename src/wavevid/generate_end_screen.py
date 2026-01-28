#!/usr/bin/env python3
"""Generate end screen template videos for different aspect ratios."""
import qrcode
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"
FONTS_DIR = Path(__file__).parent / "fonts"
BACKGROUNDS_DIR = Path(__file__).parent / "backgrounds"

# Default settings
DEFAULT_CONFIG = {
    "email": "tony@vibery.app",
    "url": "https://tony.edu.vibery.app",
    "cta": "Join Tony's Friends",
    "avatar_path": "/Applications/MAMP/htdocs/vibelabs/vibe-assets/toan_avatar.jpg",
    "video_bg": "blue-particles-background.mp4",
    "duration": 5,
    "fps": 30,
}

ASPECT_PRESETS = {
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
}


def create_overlay(width: int, height: int, config: dict) -> Image.Image:
    """Create transparent overlay with credits."""
    font_path = str(FONTS_DIR / "BeVietnamPro-Bold.ttf")

    # Scale font sizes based on smaller dimension
    base_size = min(width, height)
    font_cta = ImageFont.truetype(font_path, int(base_size * 0.045))
    font_email = ImageFont.truetype(font_path, int(base_size * 0.033))

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(config["url"])
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color=(0, 0, 0, 0)).convert('RGBA')
    qr_size = int(base_size * 0.185)
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    # Make QR background transparent
    qr_data = list(qr_img.getdata())
    new_qr_data = [(0, 0, 0, 0) if (p[0] == 0 and p[1] == 0 and p[2] == 0) else p for p in qr_data]
    qr_img.putdata(new_qr_data)

    # Load and prepare avatar
    avatar = Image.open(config["avatar_path"]).convert('RGBA')
    w, h = avatar.size
    crop_margin = int(min(w, h) * 0.10)
    avatar = avatar.crop((crop_margin, crop_margin, w - crop_margin, h - crop_margin))
    logo_size = int(base_size * 0.167)
    avatar = avatar.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Create circular mask
    scale = 4
    mask_large = Image.new('L', (logo_size * scale, logo_size * scale), 0)
    ImageDraw.Draw(mask_large).ellipse([0, 0, logo_size * scale - 1, logo_size * scale - 1], fill=255)
    mask = mask_large.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    avatar_circle = Image.new('RGBA', (logo_size, logo_size), (0, 0, 0, 0))
    avatar_circle.paste(avatar, (0, 0))
    avatar_circle.putalpha(mask)

    # Create overlay
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Layout
    center_x = width // 2
    total_height = logo_size + 50 + 60 + qr_size + 30 + 40  # Approximate total content height
    start_y = (height - total_height) // 2

    # Avatar
    avatar_x = center_x - logo_size // 2
    avatar_y = start_y
    overlay.paste(avatar_circle, (avatar_x, avatar_y), avatar_circle)

    # CTA
    cta_bbox = draw.textbbox((0, 0), config["cta"], font=font_cta)
    cta_w = cta_bbox[2] - cta_bbox[0]
    cta_x = center_x - cta_w // 2
    cta_y = avatar_y + logo_size + 50
    draw.text((cta_x, cta_y), config["cta"], fill=(255, 255, 255, 255), font=font_cta)

    # QR
    qr_x = center_x - qr_size // 2
    qr_y = cta_y + 80
    overlay.paste(qr_img, (qr_x, qr_y), qr_img)

    # Email
    email_bbox = draw.textbbox((0, 0), config["email"], font=font_email)
    email_w = email_bbox[2] - email_bbox[0]
    email_x = center_x - email_w // 2
    email_y = qr_y + qr_size + 30
    draw.text((email_x, email_y), config["email"], fill=(150, 150, 150, 255), font=font_email)

    return overlay


def generate_template(aspect: str, config: dict = None):
    """Generate end screen template for given aspect ratio."""
    config = {**DEFAULT_CONFIG, **(config or {})}
    width, height = ASPECT_PRESETS[aspect]

    TEMPLATES_DIR.mkdir(exist_ok=True)

    # Create overlay
    overlay = create_overlay(width, height, config)
    overlay_path = f"/tmp/end_screen_overlay_{aspect.replace(':', 'x')}.png"
    overlay.save(overlay_path)

    # Output path
    output_name = f"end_screen_{width}x{height}.mp4"
    output_path = TEMPLATES_DIR / output_name
    video_bg = BACKGROUNDS_DIR / config["video_bg"]

    # Generate video with FFmpeg
    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', '-1',
        '-i', str(video_bg),
        '-i', overlay_path,
        '-filter_complex',
        f'[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[bg];'
        f'[bg][1:v]overlay=0:0:format=auto[out]',
        '-map', '[out]',
        '-t', str(config["duration"]),
        '-r', str(config["fps"]),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '18',
        '-pix_fmt', 'yuv420p',
        str(output_path)
    ]

    print(f"Generating {aspect} template ({width}x{height})...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  Saved: {output_path}")
        return str(output_path)
    else:
        print(f"  Error: {result.stderr}")
        return None


def generate_all_templates(config: dict = None):
    """Generate templates for all aspect ratios."""
    for aspect in ASPECT_PRESETS:
        generate_template(aspect, config)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        aspect = sys.argv[1]
        if aspect in ASPECT_PRESETS:
            generate_template(aspect)
        elif aspect == "all":
            generate_all_templates()
        else:
            print(f"Unknown aspect ratio: {aspect}")
            print(f"Available: {', '.join(ASPECT_PRESETS.keys())}, all")
    else:
        generate_all_templates()
