"""Frame generation and video output via FFmpeg."""
import os
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
    """Load and prepare circular avatar with clean edge and border."""
    img = Image.open(path).convert('RGBA')

    # Crop center 90% of image to remove edge artifacts from source
    w, h = img.size
    crop_margin = int(min(w, h) * 0.05)
    img = img.crop((crop_margin, crop_margin, w - crop_margin, h - crop_margin))

    # Resize to target size
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Create anti-aliased circular mask at higher resolution
    scale = 4  # Supersampling factor
    mask_size = size * scale
    mask = Image.new('L', (mask_size, mask_size), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, mask_size - 1, mask_size - 1], fill=255)
    # Downsample for anti-aliasing
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    # Apply mask to avatar
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
    """Extract frames from video file, yielding PIL Images. Uses cover/fill scaling."""
    cmd = [
        'ffmpeg', '-i', video_path,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}',
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


def smart_wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wrap text with smarter line breaking - prefer breaks after punctuation, avoid orphans."""
    # First check if text fits on one line
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_width:
        return [text]

    words = text.split()
    if len(words) <= 2:
        return wrap_text(text, font, max_width, draw)

    # Try to find natural break points (after punctuation)
    punctuation = {'?', '!', '.', ',', '-', '—', ':'}
    best_break = None

    for i, word in enumerate(words[:-1]):
        if word[-1] in punctuation:
            # Test if first part fits
            first_part = ' '.join(words[:i+1])
            bbox = draw.textbbox((0, 0), first_part, font=font)
            if bbox[2] - bbox[0] <= max_width:
                best_break = i + 1

    if best_break and best_break < len(words) - 1:
        # Use punctuation break
        line1 = ' '.join(words[:best_break])
        line2 = ' '.join(words[best_break:])
        # Check if line2 fits, otherwise wrap it too
        bbox = draw.textbbox((0, 0), line2, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return [line1, line2]
        else:
            return [line1] + smart_wrap_text(line2, font, max_width, draw)

    # No good punctuation break - use balanced split (avoid orphan)
    mid = len(words) // 2
    # Try to balance line lengths
    best_split = mid
    best_diff = float('inf')

    for i in range(max(1, mid - 2), min(len(words) - 1, mid + 3)):
        part1 = ' '.join(words[:i])
        part2 = ' '.join(words[i:])
        bbox1 = draw.textbbox((0, 0), part1, font=font)
        bbox2 = draw.textbbox((0, 0), part2, font=font)
        w1, w2 = bbox1[2] - bbox1[0], bbox2[2] - bbox2[0]
        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            if diff < best_diff:
                best_diff = diff
                best_split = i

    line1 = ' '.join(words[:best_split])
    line2 = ' '.join(words[best_split:])

    # Verify both fit
    bbox1 = draw.textbbox((0, 0), line1, font=font)
    bbox2 = draw.textbbox((0, 0), line2, font=font)

    if bbox1[2] - bbox1[0] > max_width:
        return wrap_text(text, font, max_width, draw)
    if bbox2[2] - bbox2[0] > max_width:
        return [line1] + smart_wrap_text(line2, font, max_width, draw)

    return [line1, line2]


def draw_intro_title(img: Image.Image, title: str, font_path: str, width: int, height: int,
                     title_color: str = '#ffffff', subtitle: str = None,
                     frame_idx: int = 0, fps: int = 30, animations: dict = None) -> Image.Image:
    """Draw centered title text on intro frame with optional subtitle and animations.

    Args:
        animations: dict with 'title' and 'subtitle' Animation objects
    """
    from .animations import AnimationState, intro_title_animation

    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Get animation states
    time = frame_idx / fps
    if animations is None:
        animations = intro_title_animation()

    title_state = animations.get('title', None)
    subtitle_state = animations.get('subtitle', None)

    title_anim = title_state.get_state(time, fps) if title_state else AnimationState()
    sub_anim = subtitle_state.get_state(time, fps) if subtitle_state else AnimationState()

    # Parse title color
    color_hex = title_color.lstrip('#')
    base_text_color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))

    # Calculate shadow color (opposite luminance)
    luminance = (base_text_color[0] * 0.299 + base_text_color[1] * 0.587 + base_text_color[2] * 0.114) / 255
    base_shadow_color = (0, 0, 0) if luminance > 0.5 else (255, 255, 255)

    # Calculate font size based on image dimensions
    base_font_size = max(48, width // 15)
    subtitle_base_font_size = int(base_font_size * 0.5)

    # Apply scale to font size for title
    font_size = int(base_font_size * title_anim.scale)
    subtitle_font_size = int(subtitle_base_font_size * sub_anim.scale)

    try:
        font = ImageFont.truetype(font_path, font_size)
        subtitle_font = ImageFont.truetype(font_path, subtitle_font_size)
        # Also load base size fonts for layout calculation
        base_font = ImageFont.truetype(font_path, base_font_size)
        base_subtitle_font = ImageFont.truetype(font_path, subtitle_base_font_size)
    except (OSError, IOError):
        font = get_font(font_size)
        subtitle_font = get_font(subtitle_font_size)
        base_font = get_font(base_font_size)
        base_subtitle_font = get_font(subtitle_base_font_size)

    # Create overlay for compositing with opacity
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Wrap title text with smart wrapping (use base font for consistent layout)
    max_width = int(width * 0.8)
    lines = smart_wrap_text(title, base_font, max_width, draw)

    # Calculate title height using BASE font (for consistent positioning)
    base_line_heights = []
    base_line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=base_font)
        base_line_widths.append(bbox[2] - bbox[0])
        base_line_heights.append(bbox[3] - bbox[1])

    # Calculate ACTUAL line dimensions with scaled font
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    line_spacing = 10
    base_title_height = sum(base_line_heights) + line_spacing * (len(lines) - 1)

    # Calculate subtitle dimensions if provided (base size)
    base_subtitle_height = 0
    base_subtitle_width = 0
    subtitle_gap = 60
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=base_subtitle_font)
        base_subtitle_width = bbox[2] - bbox[0]
        base_subtitle_height = bbox[3] - bbox[1]

    # Total content height (base)
    total_height = base_title_height
    if subtitle:
        total_height += subtitle_gap + base_subtitle_height

    # Center vertically (base position)
    base_start_y = (height - total_height) // 2

    # Apply title opacity to colors
    title_opacity = int(255 * title_anim.opacity)
    text_color = base_text_color + (title_opacity,)
    shadow_opacity = int(180 * title_anim.opacity) if luminance > 0.5 else int(120 * title_anim.opacity)
    shadow_color = base_shadow_color + (shadow_opacity,)

    # Draw title lines centered with shadow
    current_base_y = base_start_y
    for i, line in enumerate(lines):
        # Calculate base center position
        base_line_x = (width - base_line_widths[i]) // 2
        base_line_y = current_base_y

        # Adjust for scale (center the scaled text on the base position)
        scale_offset_x = (line_widths[i] - base_line_widths[i]) // 2
        scale_offset_y = (line_heights[i] - base_line_heights[i]) // 2

        line_x = base_line_x - scale_offset_x + int(title_anim.offset_x)
        line_y = base_line_y - scale_offset_y + int(title_anim.offset_y)

        # Shadow
        draw.text((line_x + 2, line_y + 2), line, font=font, fill=shadow_color)
        # Main text
        draw.text((line_x, line_y), line, font=font, fill=text_color)

        current_base_y += base_line_heights[i] + line_spacing

    # Draw subtitle if provided
    if subtitle:
        # Apply subtitle opacity
        sub_opacity = int(255 * 0.7 * sub_anim.opacity)
        subtitle_color = tuple(int(c * 0.7) for c in base_text_color) + (sub_opacity,)
        sub_shadow_opacity = int(shadow_opacity * sub_anim.opacity)
        sub_shadow_color = base_shadow_color + (sub_shadow_opacity,)

        # Get actual subtitle dimensions
        bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        actual_sub_width = bbox[2] - bbox[0]
        actual_sub_height = bbox[3] - bbox[1]

        # Base position
        base_subtitle_y = current_base_y + subtitle_gap - line_spacing
        base_subtitle_x = (width - base_subtitle_width) // 2

        # Adjust for scale
        scale_offset_x = (actual_sub_width - base_subtitle_width) // 2
        scale_offset_y = (actual_sub_height - base_subtitle_height) // 2

        subtitle_x = base_subtitle_x - scale_offset_x + int(sub_anim.offset_x)
        subtitle_y = base_subtitle_y - scale_offset_y + int(sub_anim.offset_y)

        # Shadow
        draw.text((subtitle_x + 1, subtitle_y + 1), subtitle, font=subtitle_font, fill=sub_shadow_color)
        # Main text
        draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=subtitle_color)

    # Composite overlay onto image
    img = Image.alpha_composite(img, overlay)
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
    intro_subtitle: str = None,
    intro_static: bool = False,
    intro_avatar: str = None,
    intro_bg: str = None,
    intro_font: str = None,
    intro_title_color: str = '#ffffff',
    intro_clip_duration: float = 3.0,
    bg_music: str = None,
    bg_music_volume: int = 15,
    thumbnail: str = None,
    end_screen: bool = False,
    end_screen_duration: float = 5.0,
    preset: str = 'ultrafast',
    threads: int = 0,
    wave_sync: float = 0.0,
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
    # Pass avatar_size to radial visualizer so it can align with avatar
    if style == 'radial' and avatar_path:
        actual_avatar_size = avatar_size if avatar_size else min(width, height) // 4
        visualizer = visualizer_class(width, height, wave_color, avatar_size=actual_avatar_size)
    else:
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
            mode_str = "static" if intro_static else "animated"
            progress_callback(f"Preparing intro clip ({intro_clip_frame_count} frames, {mode_str})...")

        # Setup intro animations (or static)
        from .animations import intro_title_animation, NoAnimation
        if intro_static:
            intro_animations = {'title': NoAnimation(), 'subtitle': NoAnimation()}
        else:
            intro_animations = intro_title_animation(
                title_duration=1.0,
                subtitle_delay=0.3,
                subtitle_duration=0.5
            )

        # Load intro avatar if provided (for static mode)
        intro_avatar_img = None
        intro_avatar_size = None
        if intro_avatar and intro_static:
            intro_avatar_size = min(width, height) // 5  # Slightly smaller for intro
            intro_avatar_img = load_avatar(intro_avatar, intro_avatar_size)

        # Load intro background (image or video)
        if intro_bg and is_video_file(intro_bg):
            # Extract frames from video background
            frame_idx = 0
            for frame in extract_video_frames(intro_bg, width, height, fps, intro_clip_frame_count):
                intro_frame = draw_intro_title(
                    frame, intro_title, intro_font, width, height, intro_title_color, intro_subtitle,
                    frame_idx=frame_idx, fps=fps, animations=intro_animations
                )
                # Add avatar for static intro
                if intro_avatar_img:
                    ax_intro = (width - intro_avatar_img.width) // 2
                    ay_intro = height // 4 - intro_avatar_img.height // 2  # Upper area
                    if intro_frame.mode != 'RGBA':
                        intro_frame = intro_frame.convert('RGBA')
                    intro_frame.paste(intro_avatar_img, (ax_intro, ay_intro), intro_avatar_img)
                intro_clip_frames_list.append(intro_frame)
                frame_idx += 1
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

            if intro_static:
                # Static mode: generate one frame and repeat
                intro_frame = draw_intro_title(
                    intro_bg_img.copy(), intro_title, intro_font, width, height, intro_title_color, intro_subtitle,
                    frame_idx=999, fps=fps, animations=intro_animations
                )
                # Add avatar for static intro
                if intro_avatar_img:
                    ax_intro = (width - intro_avatar_img.width) // 2
                    ay_intro = height // 4 - intro_avatar_img.height // 2
                    if intro_frame.mode != 'RGBA':
                        intro_frame = intro_frame.convert('RGBA')
                    intro_frame.paste(intro_avatar_img, (ax_intro, ay_intro), intro_avatar_img)
                intro_clip_frames_list = [intro_frame] * intro_clip_frame_count
            else:
                # Animated mode: generate each frame
                for frame_idx in range(intro_clip_frame_count):
                    bg_copy = intro_bg_img.copy()
                    intro_frame = draw_intro_title(
                        bg_copy, intro_title, intro_font, width, height, intro_title_color, intro_subtitle,
                        frame_idx=frame_idx, fps=fps, animations=intro_animations
                    )
                    intro_clip_frames_list.append(intro_frame)

    # Calculate total frames
    # Main audio starts immediately after intro clip ends
    # End screen is concatenated separately (not rendered frame by frame)
    end_screen_sec = end_screen_duration if end_screen else 0
    total_frames = intro_clip_frame_count + n_frames

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

    # Add intro/outro/bg_music inputs
    input_idx = 2  # Next input index after video (0) and main audio (1)
    intro_idx = None
    outro_idx = None
    bg_music_idx = None

    if intro_sound:
        ffmpeg_cmd.extend(['-i', intro_sound])
        intro_idx = input_idx
        input_idx += 1

    if outro_sound:
        ffmpeg_cmd.extend(['-i', outro_sound])
        outro_idx = input_idx
        input_idx += 1

    if bg_music:
        # Use stream_loop to loop the background music
        ffmpeg_cmd.extend(['-stream_loop', '-1', '-i', bg_music])
        bg_music_idx = input_idx
        input_idx += 1

    ffmpeg_cmd.extend([
        '-c:v', 'libx264',
        '-preset', preset,
        '-tune', 'animation',    # Better for generated content
        '-crf', '23',
    ])

    # Add thread control if specified
    if threads > 0:
        ffmpeg_cmd.extend(['-threads', str(threads)])

    # Build audio filter
    # Strategy:
    # - Normalize all audio sources with loudnorm for consistent volume
    # - Intro clip: visual only, audio starts after intro clip
    # - Intro sound: fadeIn 0.5s, play intro_duration solo, then fadeOut 10s while main starts
    # - Main: delayed by intro_clip + intro_duration, fades in over 3s while intro fades out
    # - Outro: fadeIn 10s before end, play 5s after main, fadeOut 0.5s
    # - Background music: loops throughout, low volume, fade in/out at edges
    volume_factor = volume / 100
    bg_music_factor = bg_music_volume / 100 if bg_music else 0
    main_duration_sec = duration  # from load_audio
    # Total audio delay = intro clip duration + intro sound duration
    intro_clip_delay_ms = int(intro_clip_duration * 1000) if intro_title else 0
    intro_sound_delay_ms = int(intro_duration * 1000) if intro_sound else 0
    total_audio_delay_ms = intro_clip_delay_ms + intro_sound_delay_ms
    intro_trim = intro_duration + 10  # solo + fadeout overlap

    # Calculate total video duration for audio mixing
    # End screen duration is configurable
    total_video_duration = main_duration_sec + (intro_clip_duration if intro_title else 0) + end_screen_sec

    if intro_sound or outro_sound or intro_title or bg_music:
        filter_parts = []

        # Timeline:
        # 0s: Intro clip starts, intro music starts
        # intro_clip_duration: Intro clip ends, waveform starts, main audio starts
        # intro_clip_duration + intro_duration: Intro music fully faded out
        # total_video_duration - 10: Outro starts fading in
        # total_video_duration: Video ends, outro continues 5s
        #
        # Main audio: starts at intro_clip_duration, full volume
        # Intro music: starts at 0, fades out starting at intro_clip_duration
        # Outro music: fades in 10s before end, plays 5s after
        #
        # acompressor: final compression to prevent clipping
        # Note: dynaudnorm removed from main/bg audio as it amplifies background noise

        if intro_sound:
            # Main audio: boost volume, delay for intro clip
            filter_parts.append(f'[1:a]volume={volume_factor * 2.5},adelay={intro_clip_delay_ms}|{intro_clip_delay_ms}[main]')
        elif intro_title:
            # No intro sound but have intro clip: delay
            filter_parts.append(f'[1:a]volume={volume_factor},afade=t=in:st=0:d=2,adelay={intro_clip_delay_ms}|{intro_clip_delay_ms}[main]')
        else:
            # No intro: start immediately
            filter_parts.append(f'[1:a]volume={volume_factor},afade=t=in:st=0:d=2[main]')

        # Build the mix chain - start with main
        current_mix = 'main'

        if intro_sound and outro_sound:
            # Intro sound: normalize, then volume/fades
            intro_fade_out_start = intro_clip_duration
            filter_parts.append(f'[{intro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.3,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_fade_out_start}:d={intro_duration}[intro]')
            # Outro: fade in 5s before main audio ends, continue through end screen
            # Total duration = 5s overlap + end_screen_sec, fade out last 2s
            outro_total_duration = 5 + end_screen_sec + 2  # overlap + end screen + tail
            outro_start_time = max(0, total_video_duration - end_screen_sec - 5)
            outro_delay_ms = int(outro_start_time * 1000)
            outro_fade_out_start = max(0, outro_total_duration - 3)
            filter_parts.append(f'[{outro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.35,atrim=0:{outro_total_duration},afade=t=in:st=0:d=3,afade=t=out:st={outro_fade_out_start}:d=3,adelay={outro_delay_ms}|{outro_delay_ms}[outro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[with_intro]')
            filter_parts.append('[with_intro][outro]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'
        elif intro_sound:
            # Intro sound: normalize, then volume/fades
            intro_fade_out_start = intro_clip_duration
            filter_parts.append(f'[{intro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.3,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_fade_out_start}:d={intro_duration}[intro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'
        elif outro_sound:
            # Outro only: fade in 5s before main ends, continue through end screen
            outro_total_duration = 5 + end_screen_sec + 2
            outro_start_time = max(0, total_video_duration - end_screen_sec - 5)
            outro_delay_ms = int(outro_start_time * 1000)
            outro_fade_out_start = max(0, outro_total_duration - 3)
            filter_parts.append(f'[{outro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.35,atrim=0:{outro_total_duration},afade=t=in:st=0:d=3,afade=t=out:st={outro_fade_out_start}:d=3,adelay={outro_delay_ms}|{outro_delay_ms}[outro]')
            filter_parts.append('[main][outro]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'

        # Add background music if provided
        if bg_music:
            # Background music: normalize, then volume/fades
            # If outro exists, fade out bg music when outro starts (5s before main ends)
            bg_music_delay_ms = intro_clip_delay_ms
            if outro_sound:
                # Stop bg music when outro starts (fade out 3s before outro)
                bg_music_duration = main_duration_sec - 5  # End 5s before main audio ends
                fade_out_start = max(0, bg_music_duration - 3)
            else:
                bg_music_duration = main_duration_sec + 5
                fade_out_start = max(0, bg_music_duration - 5)
            filter_parts.append(f'[{bg_music_idx}:a]atrim=0:{bg_music_duration},volume={bg_music_factor},afade=t=in:st=0:d=3,afade=t=out:st={fade_out_start}:d=3,adelay={bg_music_delay_ms}|{bg_music_delay_ms}[bgm]')
            # Mix bg music with current mix, then apply final compressor
            filter_parts.append(f'[{current_mix}][bgm]amix=inputs=2:duration=first:weights=1 1:normalize=0,acompressor=threshold=-20dB:ratio=4:attack=5:release=50[aout]')
        else:
            # No bg music: apply final compressor
            filter_parts.append(f'[{current_mix}]acompressor=threshold=-20dB:ratio=4:attack=5:release=50[aout]')

        ffmpeg_cmd.extend(['-filter_complex', ';'.join(filter_parts), '-map', '0:v', '-map', '[aout]'])
    elif volume != 100:
        ffmpeg_cmd.extend(['-af', f'volume={volume_factor}'])

    ffmpeg_cmd.extend([
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
    ])
    # Only use -shortest if no end_screen (otherwise we need audio to extend for outro)
    if not end_screen:
        ffmpeg_cmd.append('-shortest')
    ffmpeg_cmd.append(output_video)

    # Debug: print ffmpeg command
    if progress_callback:
        progress_callback(f"FFmpeg cmd: {' '.join(ffmpeg_cmd[:20])}...")

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    # Pre-compute avatar position
    ax = ay = None
    if avatar:
        ax = (width - avatar.width) // 2
        ay = (height - avatar.height) // 2

    # Pre-build subtitle lookup table for O(1) access per frame
    # Subtitles sync with main audio which starts after intro clip
    subtitle_offset_frames = intro_clip_frame_count
    subtitle_lookup = {}
    if subtitles:
        for sub in subtitles:
            start_frame = int(sub['start_ms'] * fps / 1000) + subtitle_offset_frames
            end_frame = int(sub['end_ms'] * fps / 1000) + subtitle_offset_frames
            for f in range(start_frame, end_frame + 1):
                if f not in subtitle_lookup:  # First match wins
                    subtitle_lookup[f] = sub['text']

    # Generate thumbnail from intro frame after animation completes
    if thumbnail:
        if progress_callback:
            progress_callback(f"Generating thumbnail: {thumbnail}")
        if intro_clip_frames_list:
            # Use frame after animation completes (around 2 seconds in, or last frame if shorter)
            thumb_idx = min(int(fps * 2), len(intro_clip_frames_list) - 1)
            thumb_frame = intro_clip_frames_list[thumb_idx].copy()
        else:
            # Generate first waveform frame
            thumb_frame = visualizer.render_frame(background, frame_data, 0)
            if avatar:
                if thumb_frame.mode != 'RGBA':
                    thumb_frame = thumb_frame.convert('RGBA')
                thumb_frame.paste(avatar, (ax, ay), avatar)
        if thumb_frame.mode != 'RGB':
            thumb_frame = thumb_frame.convert('RGB')
        thumb_frame.save(thumbnail, quality=95)

    # Cache base frame with avatar for static backgrounds (non-video)
    # This avoids re-compositing avatar on every frame
    cached_base = None
    use_cache = avatar and not is_video_file(bg_value) if bg_type == 'image' else avatar

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
            # Visualizer syncs with main audio - add small delay for better sync
            # Visualizer frame = current frame - intro frames + sync offset
            # Main audio starts at intro_clip_frame_count (delayed by intro_clip_duration in ffmpeg)
            # wave_sync: positive = delay wave (wave behind audio), negative = advance wave (wave ahead of audio)
            sync_offset_frames = int(wave_sync * fps)
            data_idx = i - intro_clip_frame_count - sync_offset_frames
            data_idx = max(0, min(data_idx, n_frames - 1))  # Clamp to valid range

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

    if process.returncode != 0:
        if progress_callback:
            progress_callback("Error rendering video")
        return False, 0

    # Concatenate end screen if enabled
    if end_screen:
        if progress_callback:
            progress_callback("Adding end screen...")

        # Find template for this resolution
        templates_dir = Path(__file__).parent / "templates"
        template_path = templates_dir / f"end_screen_{width}x{height}.mp4"

        if template_path.exists():
            # Temp output for concatenated video
            temp_output = output_video + '.temp.mp4'

            # Concat videos - main video audio already has outro extending into end screen duration
            concat_cmd = [
                'ffmpeg', '-y',
                '-i', output_video,
                '-i', str(template_path),
                '-filter_complex',
                f'[0:v][1:v]concat=n=2:v=1:a=0[outv]',
                '-map', '[outv]', '-map', '0:a',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'copy',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                temp_output
            ]
            concat_result = subprocess.run(concat_cmd, capture_output=True)

            if concat_result.returncode == 0:
                # Replace original with concatenated
                os.replace(temp_output, output_video)
            else:
                if progress_callback:
                    progress_callback("Warning: Could not add end screen")
                # Clean up temp file if it exists
                if os.path.exists(temp_output):
                    os.unlink(temp_output)
        else:
            if progress_callback:
                progress_callback(f"Warning: End screen template not found for {width}x{height}")

    # Embed thumbnail as MP4 cover art if provided
    if thumbnail and os.path.exists(thumbnail):
        if progress_callback:
            progress_callback("Embedding cover image...")

        temp_output = output_video + '.cover.mp4'
        cover_cmd = [
            'ffmpeg', '-y',
            '-i', output_video,
            '-i', thumbnail,
            '-map', '0',
            '-map', '1',
            '-c', 'copy',
            '-disposition:v:1', 'attached_pic',
            temp_output
        ]
        cover_result = subprocess.run(cover_cmd, capture_output=True)

        if cover_result.returncode == 0:
            os.replace(temp_output, output_video)
        else:
            # Failed to embed, clean up
            if os.path.exists(temp_output):
                os.unlink(temp_output)

    if progress_callback:
        progress_callback("Done!")

    # Calculate total video duration
    total_video_sec = total_frames / fps + end_screen_sec
    return True, total_video_sec


def render_audio(
    input_audio: str,
    output_audio: str,
    volume: int = 100,
    intro_sound: str = None,
    intro_duration: float = 3.0,
    outro_sound: str = None,
    intro_clip_duration: float = 0.0,
    bg_music: str = None,
    bg_music_volume: int = 15,
    end_screen_duration: float = 0.0,
    progress_callback=None
):
    """Render audio mix only (no video)."""

    if progress_callback:
        progress_callback("Loading audio...")

    # Get audio duration
    y, sr, duration = load_audio(input_audio)

    if progress_callback:
        progress_callback(f"Audio duration: {duration:.1f}s")

    # Calculate timing
    volume_factor = volume / 100
    bg_music_factor = bg_music_volume / 100 if bg_music else 0
    intro_clip_delay_ms = int(intro_clip_duration * 1000) if intro_clip_duration > 0 else 0
    intro_trim = intro_duration + 10
    end_screen_sec = end_screen_duration
    total_audio_duration = duration + intro_clip_duration + end_screen_sec

    # Build FFmpeg command
    ffmpeg_cmd = ['ffmpeg', '-y', '-i', input_audio]

    input_idx = 1
    intro_idx = None
    outro_idx = None
    bg_music_idx = None

    if intro_sound:
        ffmpeg_cmd.extend(['-i', intro_sound])
        intro_idx = input_idx
        input_idx += 1

    if outro_sound:
        ffmpeg_cmd.extend(['-i', outro_sound])
        outro_idx = input_idx
        input_idx += 1

    if bg_music:
        ffmpeg_cmd.extend(['-stream_loop', '-1', '-i', bg_music])
        bg_music_idx = input_idx
        input_idx += 1

    # Build audio filter
    if intro_sound or outro_sound or intro_clip_duration > 0 or bg_music:
        filter_parts = []

        if intro_sound:
            filter_parts.append(f'[0:a]volume={volume_factor * 2.5},adelay={intro_clip_delay_ms}|{intro_clip_delay_ms}[main]')
        elif intro_clip_duration > 0:
            filter_parts.append(f'[0:a]volume={volume_factor},afade=t=in:st=0:d=2,adelay={intro_clip_delay_ms}|{intro_clip_delay_ms}[main]')
        else:
            filter_parts.append(f'[0:a]volume={volume_factor},afade=t=in:st=0:d=2[main]')

        current_mix = 'main'

        if intro_sound and outro_sound:
            intro_fade_out_start = intro_clip_duration
            filter_parts.append(f'[{intro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.3,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_fade_out_start}:d={intro_duration}[intro]')
            outro_total_duration = 5 + end_screen_sec + 2
            outro_start_time = max(0, total_audio_duration - end_screen_sec - 5)
            outro_delay_ms = int(outro_start_time * 1000)
            outro_fade_out_start = max(0, outro_total_duration - 3)
            filter_parts.append(f'[{outro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.35,atrim=0:{outro_total_duration},afade=t=in:st=0:d=3,afade=t=out:st={outro_fade_out_start}:d=3,adelay={outro_delay_ms}|{outro_delay_ms}[outro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[with_intro]')
            filter_parts.append('[with_intro][outro]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'
        elif intro_sound:
            intro_fade_out_start = intro_clip_duration
            filter_parts.append(f'[{intro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.3,atrim=0:{intro_trim},afade=t=in:st=0:d=0.5,afade=t=out:st={intro_fade_out_start}:d={intro_duration}[intro]')
            filter_parts.append('[intro][main]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'
        elif outro_sound:
            outro_total_duration = 5 + end_screen_sec + 2
            outro_start_time = max(0, total_audio_duration - end_screen_sec - 5)
            outro_delay_ms = int(outro_start_time * 1000)
            outro_fade_out_start = max(0, outro_total_duration - 3)
            filter_parts.append(f'[{outro_idx}:a]dynaudnorm=p=0.9:s=5,volume=0.35,atrim=0:{outro_total_duration},afade=t=in:st=0:d=3,afade=t=out:st={outro_fade_out_start}:d=3,adelay={outro_delay_ms}|{outro_delay_ms}[outro]')
            filter_parts.append('[main][outro]amix=inputs=2:duration=longest:weights=1 1:normalize=0[premix]')
            current_mix = 'premix'

        if bg_music:
            bg_music_delay_ms = intro_clip_delay_ms
            if outro_sound:
                bg_music_duration = duration - 5
                fade_out_start = max(0, bg_music_duration - 3)
            else:
                bg_music_duration = duration + 5
                fade_out_start = max(0, bg_music_duration - 5)
            filter_parts.append(f'[{bg_music_idx}:a]atrim=0:{bg_music_duration},volume={bg_music_factor},afade=t=in:st=0:d=3,afade=t=out:st={fade_out_start}:d=3,adelay={bg_music_delay_ms}|{bg_music_delay_ms}[bgm]')
            filter_parts.append(f'[{current_mix}][bgm]amix=inputs=2:duration=first:weights=1 1:normalize=0,acompressor=threshold=-20dB:ratio=4:attack=5:release=50[aout]')
        else:
            filter_parts.append(f'[{current_mix}]acompressor=threshold=-20dB:ratio=4:attack=5:release=50[aout]')

        ffmpeg_cmd.extend(['-filter_complex', ';'.join(filter_parts), '-map', '[aout]'])
    elif volume != 100:
        ffmpeg_cmd.extend(['-af', f'volume={volume_factor}'])

    # Output format based on extension
    ext = Path(output_audio).suffix.lower()
    if ext == '.mp3':
        ffmpeg_cmd.extend(['-c:a', 'libmp3lame', '-b:a', '192k'])
    elif ext == '.m4a' or ext == '.aac':
        ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    elif ext == '.wav':
        ffmpeg_cmd.extend(['-c:a', 'pcm_s16le'])
    else:
        ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '192k'])

    ffmpeg_cmd.append(output_audio)

    if progress_callback:
        progress_callback("Mixing audio...")

    result = subprocess.run(ffmpeg_cmd, capture_output=True)

    if result.returncode != 0:
        if progress_callback:
            progress_callback(f"Error: {result.stderr.decode()[:200]}")
        return False, 0

    if progress_callback:
        progress_callback("Done!")

    return True, total_audio_duration
