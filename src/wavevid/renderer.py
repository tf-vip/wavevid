"""Frame generation and video output via FFmpeg."""
import subprocess
import numpy as np
from pathlib import Path
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


def is_video_file(path: str) -> bool:
    """Check if file is a video based on extension."""
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    return Path(path).suffix.lower() in video_exts


def get_video_frame_count(video_path: str, fps: int) -> int:
    """Get approximate frame count for a video at given fps."""
    import json
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        duration = float(data['format'].get('duration', 0))
        return int(duration * fps)
    return 0


def extract_video_frames(video_path: str, width: int, height: int, fps: int, max_frames: int):
    """Extract frames from video file, yielding PIL Images."""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
        '-r', str(fps),
        '-f', 'rawvideo',
        '-pix_fmt', 'rgb24',
        '-frames:v', str(max_frames),
        '-'
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_size = width * height * 3

    frames_read = 0
    while frames_read < max_frames:
        raw = process.stdout.read(frame_size)
        if len(raw) < frame_size:
            break
        frame = Image.frombytes('RGB', (width, height), raw)
        yield frame
        frames_read += 1

    process.stdout.close()
    process.wait()


def draw_intro_title(img: Image.Image, title: str, font_path: str, width: int, height: int, title_color: str = '#ffffff') -> Image.Image:
    """Draw centered title text on intro frame."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    draw = ImageDraw.Draw(img)

    # Parse title color
    color_hex = title_color.lstrip('#')
    text_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4)) + (255,)

    # Calculate shadow color (opposite luminance)
    luminance = (text_color[0] * 0.299 + text_color[1] * 0.587 + text_color[2] * 0.114) / 255
    shadow_color = (0, 0, 0, 180) if luminance > 0.5 else (255, 255, 255, 120)

    # Calculate font size based on image dimensions (roughly 1/10 of width for good readability)
    font_size = max(48, width // 15)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except (OSError, IOError):
        font = get_font(font_size)

    # Wrap text if needed
    max_width = int(width * 0.8)
    lines = wrap_text(title, font, max_width, draw)

    # Calculate total height
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 10
    total_height = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Center vertically
    start_y = (height - total_height) // 2

    # Draw each line centered with shadow for readability
    current_y = start_y
    for i, line in enumerate(lines):
        line_x = (width - line_widths[i]) // 2
        # Shadow
        draw.text((line_x + 2, current_y + 2), line, font=font, fill=shadow_color)
        # Main text
        draw.text((line_x, current_y), line, font=font, fill=text_color)
        current_y += line_heights[i] + line_spacing

    return img


def blend_frames(frame1: Image.Image, frame2: Image.Image, alpha: float) -> Image.Image:
    """Blend two frames together. alpha=0 is all frame1, alpha=1 is all frame2."""
    if frame1.mode != 'RGBA':
        frame1 = frame1.convert('RGBA')
    if frame2.mode != 'RGBA':
        frame2 = frame2.convert('RGBA')
    return Image.blend(frame1, frame2, alpha)


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
    intro_title: str = None,
    intro_bg: str = None,
    intro_font: str = None,
    intro_title_color: str = '#ffffff',
    intro_clip_duration: float = 3.0,
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

    # Prepare intro clip if title is provided
    intro_clip_frames_list = []
    intro_clip_frame_count = 0
    fade_duration_frames = int(fps * 0.5)  # 0.5 second fade transition

    if intro_title:
        intro_clip_frame_count = int(intro_clip_duration * fps)
        if progress_callback:
            progress_callback(f"Preparing intro clip ({intro_clip_frame_count} frames)...")

        # Load intro background (image or video)
        if intro_bg and is_video_file(intro_bg):
            # Extract frames from video background
            for frame in extract_video_frames(intro_bg, width, height, fps, intro_clip_frame_count):
                intro_frame = draw_intro_title(frame, intro_title, intro_font, width, height, intro_title_color)
                intro_clip_frames_list.append(intro_frame)
            # If video is shorter than needed, repeat last frame
            while len(intro_clip_frames_list) < intro_clip_frame_count:
                intro_clip_frames_list.append(intro_clip_frames_list[-1].copy() if intro_clip_frames_list else None)
        else:
            # Static image background
            if intro_bg:
                intro_bg_img = Image.open(intro_bg).convert('RGBA')
                intro_bg_img = intro_bg_img.resize((width, height), Image.Resampling.LANCZOS)
            else:
                # Use main background as fallback
                intro_bg_img = background.copy()
                if intro_bg_img.mode != 'RGBA':
                    intro_bg_img = intro_bg_img.convert('RGBA')

            intro_frame = draw_intro_title(intro_bg_img, intro_title, intro_font, width, height, intro_title_color)
            # Repeat static frame for entire duration
            intro_clip_frames_list = [intro_frame] * intro_clip_frame_count

    # Calculate total frames including intro padding (for audio) and intro clip
    intro_solo_ms = int(intro_duration * 1000) if intro_sound else 0
    intro_audio_frames = int(intro_solo_ms * fps / 1000)
    # Total = intro clip + main waveform frames (audio intro padding is handled separately)
    total_frames = intro_clip_frame_count + n_frames + intro_audio_frames

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
    # - Intro clip: visual only, audio starts after intro clip
    # - Intro sound: fadeIn 0.5s, play intro_duration solo, then fadeOut 10s while main starts
    # - Main: delayed by intro_clip + intro_duration, fades in over 3s while intro fades out
    # - Outro: fadeIn 10s before end, play 5s after main, fadeOut 0.5s
    volume_factor = volume / 100
    main_duration_sec = duration  # from load_audio
    # Total audio delay = intro clip duration + intro sound duration
    intro_clip_delay_ms = int(intro_clip_duration * 1000) if intro_title else 0
    intro_sound_delay_ms = int(intro_duration * 1000) if intro_sound else 0
    total_audio_delay_ms = intro_clip_delay_ms + intro_sound_delay_ms
    intro_trim = intro_duration + 10  # solo + fadeout overlap

    if intro_sound or outro_sound or intro_title:
        filter_parts = []

        if intro_sound:
            # Main audio: normalize, apply volume, delay by total delay (clip + sound), fade in
            filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume_factor},adelay={total_audio_delay_ms}|{total_audio_delay_ms},afade=t=in:st=0:d=3[main]')
        elif intro_title:
            # No intro sound but have intro clip: delay main by intro clip duration
            filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume_factor},adelay={intro_clip_delay_ms}|{intro_clip_delay_ms},afade=t=in:st=0:d=3[main]')
        else:
            # No intro: main starts immediately
            filter_parts.append(f'[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume={volume_factor},afade=t=in:st=0:d=3[main]')

        if intro_sound and outro_sound:
            # Intro sound: normalize, lower volume (0.6), delay by intro clip, fadeIn 0.5s, fadeOut starting at intro_duration for 10s
            intro_sound_start_delay = intro_clip_delay_ms
            filter_parts.append(f'[{intro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_duration}:d=10,adelay={intro_sound_start_delay}|{intro_sound_start_delay}[intro]')
            # Outro: normalize, lower volume (0.6), fadeIn 10s, fadeOut last 0.5s
            filter_parts.append(f'[{outro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:15.5,afade=t=in:st=0:d=10,afade=t=out:st=15:d=0.5[outro]')
            # Delay outro to start 10s before main ends (account for main's delay)
            outro_delay_ms = int(max(0, (main_duration_sec - 10)) * 1000) + total_audio_delay_ms
            filter_parts.append(f'[outro]adelay={outro_delay_ms}|{outro_delay_ms}[outro_delayed]')
            # Mix all: intro + main first
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[with_intro]')
            # Then add outro
            filter_parts.append('[with_intro][outro_delayed]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')
        elif intro_sound:
            # Intro sound only: normalize, lower volume, delay by intro clip, fades
            intro_sound_start_delay = intro_clip_delay_ms
            filter_parts.append(f'[{intro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_duration}:d=10,adelay={intro_sound_start_delay}|{intro_sound_start_delay}[intro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')
        elif outro_sound:
            # Outro only
            filter_parts.append(f'[{outro_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=0.6,atrim=0:15.5,afade=t=in:st=0:d=10,afade=t=out:st=15:d=0.5[outro]')
            outro_delay_ms = int(max(0, (main_duration_sec - 10)) * 1000) + intro_clip_delay_ms
            filter_parts.append(f'[outro]adelay={outro_delay_ms}|{outro_delay_ms}[outro_delayed]')
            filter_parts.append('[main][outro_delayed]amix=inputs=2:duration=longest:weights=1 1:normalize=0[aout]')
        else:
            # Intro clip only, no intro/outro sound - just use delayed main
            filter_parts.append('[main]anull[aout]')

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
    # Account for intro clip + audio delay - subtitles sync with main audio
    subtitle_offset_frames = intro_clip_frame_count + intro_audio_frames
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
        # Determine which phase we're in
        if intro_clip_frame_count > 0 and i < intro_clip_frame_count:
            # Phase 1: Intro clip frames
            intro_frame = intro_clip_frames_list[i]

            # Check if we're in the fade transition zone (last fade_duration_frames of intro)
            fade_start = intro_clip_frame_count - fade_duration_frames
            if i >= fade_start:
                # Blend intro frame with first waveform frame
                fade_progress = (i - fade_start) / fade_duration_frames
                waveform_frame = visualizer.render_frame(background, frame_data, 0)
                if avatar:
                    if waveform_frame.mode != 'RGBA':
                        waveform_frame = waveform_frame.convert('RGBA')
                    waveform_frame.paste(avatar, (ax, ay), avatar)
                frame = blend_frames(intro_frame, waveform_frame, fade_progress)
            else:
                frame = intro_frame
        else:
            # Phase 2: Main waveform frames (after intro clip)
            # Calculate the data index accounting for intro clip and audio delay
            main_frame_idx = i - intro_clip_frame_count
            data_idx = max(0, main_frame_idx - intro_audio_frames) if intro_audio_frames > 0 else main_frame_idx
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
