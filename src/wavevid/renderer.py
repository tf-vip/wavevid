"""Frame generation and video output via FFmpeg."""
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .audio import load_audio, get_amplitude_envelope, get_frequency_bands, get_waveform_chunks
from .backgrounds import get_background
from .visualizers import get_visualizer


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if needed."""
    # Try common system fonts
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))

    return lines if lines else [text]


def draw_subtitle(img: Image.Image, text: str, font_size: int, text_color: tuple, y_position: int) -> Image.Image:
    """Draw subtitle text with background on image, auto-wrapping long text."""
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)

    # Max width is 90% of image width
    max_width = int(img.width * 0.9)
    padding = 12
    line_spacing = 6

    # Wrap text to fit
    lines = wrap_text(text, font, max_width, draw)

    # Calculate total height
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    max_line_width = max(line_widths)

    # Adjust y_position so subtitle doesn't go off screen
    y = min(y_position, img.height - total_height - padding * 2 - 10)

    # Background box
    bg_x = (img.width - max_line_width) // 2 - padding
    bg_box = [bg_x, y - padding, bg_x + max_line_width + padding * 2, y + total_height + padding]

    # Create overlay for semi-transparent background
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(bg_box, radius=10, fill=(0, 0, 0, 180))

    # Composite
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    img = Image.alpha_composite(img, overlay)

    # Draw each line centered
    draw = ImageDraw.Draw(img)
    current_y = y
    for i, line in enumerate(lines):
        line_x = (img.width - line_widths[i]) // 2
        draw.text((line_x, current_y), line, font=font, fill=text_color)
        current_y += line_heights[i] + line_spacing

    return img


def load_avatar(path: str, size: int) -> Image.Image:
    """Load and prepare circular avatar."""
    img = Image.open(path).convert('RGBA')
    # Resize to square
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Create circular mask
    mask = Image.new('L', (size, size), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size, size], fill=255)

    # Apply mask
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0))
    output.putalpha(mask)

    return output


def render_video(
    input_audio: str,
    output_video: str,
    style: str = 'waveform',
    bg_type: str = 'color',
    bg_value: str = '#1a1a2e',
    wave_color: str = '#00ff88',
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    avatar_path: str = None,
    avatar_size: int = None,
    subtitles: list = None,
    subtitle_font_size: int = None,
    subtitle_color: str = '#ffffff',
    progress_callback=None
):
    """Render audio visualization video."""

    # Load and analyze audio
    if progress_callback:
        progress_callback("Loading audio...")
    y, sr, duration = load_audio(input_audio)

    if progress_callback:
        progress_callback("Analyzing audio...")

    # Extract audio features
    amplitude = get_amplitude_envelope(y, sr, fps)
    bands = get_frequency_bands(y, sr, fps, n_bands=64)
    waveform = get_waveform_chunks(y, sr, fps, samples_per_frame=200)

    # Ensure all arrays have same length
    n_frames = min(len(amplitude), len(bands), len(waveform))
    amplitude = amplitude[:n_frames]
    bands = bands[:n_frames]
    waveform = waveform[:n_frames]

    frame_data = {
        'amplitude': amplitude,
        'bands': bands,
        'waveform': waveform,
    }

    # Setup visualizer and background
    background = get_background(width, height, bg_type, bg_value)
    visualizer_class = get_visualizer(style)
    visualizer = visualizer_class(width, height, wave_color)

    # Load avatar if provided
    avatar = None
    if avatar_path:
        if avatar_size is None:
            avatar_size = min(width, height) // 4
        avatar = load_avatar(avatar_path, avatar_size)

    # Setup subtitle rendering
    if subtitle_font_size is None:
        subtitle_font_size = max(24, height // 20)
    subtitle_y = int(height * 0.85)

    # Parse subtitle color
    sub_color_hex = subtitle_color.lstrip('#')
    sub_color = tuple(int(sub_color_hex[i:i+2], 16) for i in (0, 2, 4)) + (255,)

    if progress_callback:
        progress_callback(f"Rendering {n_frames} frames...")

    # Setup FFmpeg pipe
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{width}x{height}',
        '-pix_fmt', 'rgb24',
        '-r', str(fps),
        '-i', '-',
        '-i', input_audio,
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_video
    ]

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Render frames
    for i in range(n_frames):
        frame = visualizer.render_frame(background, frame_data, i)

        # Overlay avatar at center
        if avatar:
            frame = frame.convert('RGBA')
            ax = (width - avatar.width) // 2
            ay = (height - avatar.height) // 2
            frame.paste(avatar, (ax, ay), avatar)

        # Draw subtitle if active
        if subtitles:
            current_ms = int(i * 1000 / fps)
            for sub in subtitles:
                if sub['start_ms'] <= current_ms <= sub['end_ms']:
                    frame = draw_subtitle(frame, sub['text'], subtitle_font_size, sub_color, subtitle_y)
                    break

        # Ensure RGB for output
        if frame.mode != 'RGB':
            frame = frame.convert('RGB')

        process.stdin.write(frame.tobytes())

        if progress_callback and i % fps == 0:
            progress_callback(f"Frame {i}/{n_frames} ({i * 100 // n_frames}%)")

    process.stdin.close()
    process.wait()

    if progress_callback:
        progress_callback("Done!")

    return process.returncode == 0
