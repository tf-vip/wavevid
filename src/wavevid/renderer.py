"""Frame generation and video output via FFmpeg."""
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from multiprocessing import Pool, cpu_count
from functools import partial
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
    volume: int = 100,
    intro_sound: str = None,
    intro_duration: float = 3.0,
    outro_sound: str = None,
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

    # Calculate total frames including intro padding
    intro_solo_ms = int(intro_duration * 1000) if intro_sound else 0
    intro_frames = int(intro_solo_ms * fps / 1000)
    total_frames = n_frames + intro_frames

    if progress_callback:
        progress_callback(f"Rendering {total_frames} frames...")

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
    ]

    # Add intro/outro inputs
    input_idx = 2  # Next input index after video (0) and main audio (1)
    intro_idx = None
    outro_idx = None

    if intro_sound:
        ffmpeg_cmd.extend(['-i', intro_sound])
        intro_idx = input_idx
        input_idx += 1

    if outro_sound:
        ffmpeg_cmd.extend(['-i', outro_sound])
        outro_idx = input_idx
        input_idx += 1

    ffmpeg_cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'ultrafast',  # Much faster encoding
        '-tune', 'animation',    # Better for generated content
        '-crf', '23',
    ])

    # Build audio filter
    # Strategy:
    # - Normalize all audio sources with loudnorm for consistent volume
    # - Intro: fadeIn 0.5s, play intro_duration solo, then fadeOut 10s while main starts
    # - Main: delayed by intro_duration, fades in over 3s while intro fades out
    # - Outro: fadeIn 10s before end, play 5s after main, fadeOut 0.5s
    volume_factor = volume / 100
    main_duration_sec = duration  # from load_audio
    intro_delay_ms = int(intro_duration * 1000) if intro_sound else 0
    intro_trim = intro_duration + 10  # solo + fadeout overlap

    if intro_sound or outro_sound:
        filter_parts = []

        if intro_sound:
            # Main audio: normalize, apply volume, delay by intro_duration, fade in
            filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume_factor},adelay={intro_delay_ms}|{intro_delay_ms},afade=t=in:st=0:d=3[main]')
        else:
            # No intro: main starts immediately
            filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume_factor},afade=t=in:st=0:d=3[main]')

        if intro_sound and outro_sound:
            # Intro: normalize, lower volume (0.6), fadeIn 0.5s, fadeOut starting at intro_duration for 10s
            filter_parts.append(f'[{intro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_duration}:d=10[intro]')
            # Outro: normalize, lower volume (0.6), fadeIn 10s, fadeOut last 0.5s
            filter_parts.append(f'[{outro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:15.5,afade=t=in:st=0:d=10,afade=t=out:st=15:d=0.5[outro]')
            # Delay outro to start 10s before main ends (account for main's delay)
            outro_delay_ms = int(max(0, (main_duration_sec - 10)) * 1000) + intro_delay_ms
            filter_parts.append(f'[outro]adelay={outro_delay_ms}|{outro_delay_ms}[outro_delayed]')
            # Mix all: intro + main first
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[with_intro]')
            # Then add outro
            filter_parts.append('[with_intro][outro_delayed]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')
        elif intro_sound:
            # Intro only: normalize, lower volume, fades
            filter_parts.append(f'[{intro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_duration}:d=10[intro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')
        else:
            # Outro only
            filter_parts.append(f'[{outro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:15.5,afade=t=in:st=0:d=10,afade=t=out:st=15:d=0.5[outro]')
            outro_delay_ms = int(max(0, (main_duration_sec - 10)) * 1000)
            filter_parts.append(f'[outro]adelay={outro_delay_ms}|{outro_delay_ms}[outro_delayed]')
            filter_parts.append('[main][outro_delayed]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')

        ffmpeg_cmd.extend(['-filter_complex', ';'.join(filter_parts), '-map', '0:v', '-map', '[aout]'])
    elif volume != 100:
        ffmpeg_cmd.extend(['-af', f'volume={volume_factor}'])

    ffmpeg_cmd.extend([
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_video
    ])

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Pre-compute avatar position
    ax = ay = None
    if avatar:
        ax = (width - avatar.width) // 2
        ay = (height - avatar.height) // 2

    # Pre-build subtitle lookup table for O(1) access per frame
    # Account for intro delay - subtitles sync with main audio which is delayed
    subtitle_offset_frames = intro_frames
    subtitle_lookup = {}
    if subtitles:
        for sub in subtitles:
            start_frame = int(sub['start_ms'] * fps / 1000) + subtitle_offset_frames
            end_frame = int(sub['end_ms'] * fps / 1000) + subtitle_offset_frames
            for f in range(start_frame, end_frame + 1):
                if f not in subtitle_lookup:  # First match wins
                    subtitle_lookup[f] = sub['text']

    # Render frames with optimizations
    report_interval = fps * 2  # Report every 2 seconds instead of every 1

    for i in range(total_frames):
        # For intro frames, use frame 0 data (static); otherwise offset by intro_frames
        data_idx = max(0, i - intro_frames) if intro_frames > 0 else i
        data_idx = min(data_idx, n_frames - 1)  # Clamp to valid range

        frame = visualizer.render_frame(background, frame_data, data_idx)

        # Overlay avatar at center
        if avatar:
            if frame.mode != 'RGBA':
                frame = frame.convert('RGBA')
            frame.paste(avatar, (ax, ay), avatar)

        # Draw subtitle if active (O(1) lookup)
        if i in subtitle_lookup:
            frame = draw_subtitle(frame, subtitle_lookup[i], subtitle_font_size, sub_color, subtitle_y)

        # Ensure RGB for output
        if frame.mode != 'RGB':
            frame = frame.convert('RGB')

        process.stdin.write(frame.tobytes())

        if progress_callback and i % report_interval == 0:
            progress_callback(f"Frame {i}/{total_frames} ({i * 100 // total_frames}%)")

    process.stdin.close()
    process.wait()

    if progress_callback:
        progress_callback("Done!")

    return process.returncode == 0
