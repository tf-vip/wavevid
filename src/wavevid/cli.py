"""CLI entry point for wavevid."""
import click
import random
from pathlib import Path
from .renderer import render_video, render_audio

# Default directories (inside package)
BACKGROUNDS_DIR = Path(__file__).parent / 'backgrounds'
SOUNDS_DIR = Path(__file__).parent / 'sounds'
FONTS_DIR = Path(__file__).parent / 'fonts'
DEFAULT_INTRO_FONT = FONTS_DIR / 'BeVietnamPro-Bold.ttf'

# Aspect ratio presets
ASPECT_PRESETS = {
    '16:9': (1920, 1080),
    '9:16': (1080, 1920),
    '1:1': (1080, 1080),
    '4:5': (1080, 1350),
}


def discover_files(directory: Path, extensions: list[str]) -> list[Path]:
    """Dynamically discover files with given extensions in directory."""
    files = []
    for ext in extensions:
        files.extend(directory.glob(f'*.{ext}'))
        files.extend(directory.glob(f'**/*.{ext}'))
    return list(set(files))


@click.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.option('-o', '--output', 'output_video', default='output.mp4', help='Output video file')
@click.option('--style', type=click.Choice(['waveform', 'radial', 'bars', 'spectrum', 'particles']), default='waveform', help='Visualization style')
@click.option('--bg', 'bg_type', type=click.Choice(['color', 'gradient', 'image', 'random']), default='color', help='Background type (random picks from backgrounds/)')
@click.option('--bg-value', default='#1a1a2e', help='Background value: hex color, "color1,color2" for gradient, or image path')
@click.option('--wave-color', default='#00ff88', help='Wave/bar color (hex or "auto" for smart detection)')
@click.option('--aspect', type=click.Choice(['16:9', '9:16', '1:1', '4:5']), help='Aspect ratio preset (overrides width/height)')
@click.option('--width', default=1920, help='Video width')
@click.option('--height', default=1080, help='Video height')
@click.option('--fps', default=30, help='Frames per second')
@click.option('--thumbnail', type=click.Path(), help='Save thumbnail image from first frame')
@click.option('--avatar', 'avatar_path', type=click.Path(exists=True), help='Avatar image to place at center')
@click.option('--avatar-size', type=int, help='Avatar size in pixels (default: 1/4 of min dimension)')
@click.option('--subtitle/--no-subtitle', default=False, help='Enable subtitle transcription via Soniox')
@click.option('--subtitle-font-size', type=int, help='Subtitle font size (default: height/20)')
@click.option('--subtitle-color', default='auto', help='Subtitle text color (hex or "auto")')
@click.option('--volume', default=100, type=int, help='Audio volume percentage (e.g., 120 for 120%)')
@click.option('--replace', 'replacements', multiple=True, help='Text replacement in subtitles (format: old=new)')
@click.option('--replace-file', type=click.Path(exists=True), help='File with replacements (one per line: old=new)')
@click.option('--intro', 'intro_sound', type=click.Path(exists=True), help='Intro sound file')
@click.option('--intro-duration', default=3.0, type=float, help='Intro solo duration in seconds before main audio starts (default: 3)')
@click.option('--outro', 'outro_sound', type=click.Path(exists=True), help='Outro sound file')
@click.option('--intro-title', help='Title text to display on intro clip')
@click.option('--intro-subtitle', help='Subtitle text below intro title')
@click.option('--intro-static/--intro-animated', default=False, help='Use static intro (no animation) for better social media thumbnails')
@click.option('--intro-bg', type=click.Path(exists=True), help='Intro background (image or video file)')
@click.option('--intro-font', type=click.Path(exists=True), help='Custom font for intro title (default: Be Vietnam Pro Bold)')
@click.option('--intro-title-color', default='auto', help='Intro title color (hex or "auto")')
@click.option('--intro-clip-duration', default=3.0, type=float, help='Intro clip duration in seconds (default: 3)')
@click.option('--bg-music', type=click.Path(exists=True), help='Background music file (loops throughout video)')
@click.option('--bg-music-volume', default=15, type=int, help='Background music volume percentage (default: 15)')
@click.option('--end-screen/--no-end-screen', default=None, help='Enable/disable end screen (default: enabled when outro is set)')
@click.option('--end-screen-duration', default=5.0, type=float, help='End screen duration in seconds (default: 5)')
@click.option('--preset', type=click.Choice(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow']), default='ultrafast', help='Encoding speed preset (ultrafast=fast/low quality, veryslow=slow/high quality)')
@click.option('--threads', type=int, default=0, help='Number of encoding threads (0=auto, based on CPU cores)')
@click.option('--wave-sync', default=0.0, type=float, help='Waveform sync offset in seconds (positive=delay wave, negative=advance wave)')
@click.option('--audio-only', is_flag=True, default=False, help='Generate audio mix only (no video rendering)')
def main(input_audio, output_video, style, bg_type, bg_value, wave_color, aspect, width, height, fps, thumbnail, avatar_path, avatar_size, subtitle, subtitle_font_size, subtitle_color, volume, replacements, replace_file, intro_sound, intro_duration, outro_sound, intro_title, intro_subtitle, intro_static, intro_bg, intro_font, intro_title_color, intro_clip_duration, bg_music, bg_music_volume, end_screen, end_screen_duration, preset, threads, wave_sync, audio_only):
    """Generate waveform video from audio file."""
    # Apply aspect ratio preset if specified
    if aspect:
        width, height = ASPECT_PRESETS[aspect]
        click.echo(f"Aspect ratio {aspect}: {width}x{height}")
    # Handle random background selection (dynamic discovery)
    if bg_type == 'random':
        bg_files = discover_files(BACKGROUNDS_DIR, ['jpg', 'jpeg', 'png', 'webp'])
        if bg_files:
            bg_value = str(random.choice(bg_files))
            bg_type = 'image'
            click.echo(f"Random background: {Path(bg_value).name}")
        else:
            click.echo("No backgrounds found, using default color")
            bg_type = 'color'
            bg_value = '#1a1a2e'

    # Handle auto colors
    temp_bg = None
    if (wave_color == 'auto' or subtitle_color == 'auto') and bg_type == 'image':
        from .backgrounds import get_background, calculate_auto_wave_color, calculate_auto_subtitle_color
        temp_bg = get_background(width, height, bg_type, bg_value)

        if wave_color == 'auto':
            wave_color = calculate_auto_wave_color(temp_bg)
            click.echo(f"Auto wave color: {wave_color}")

        if subtitle_color == 'auto':
            subtitle_color = calculate_auto_subtitle_color(temp_bg)
            click.echo(f"Auto subtitle color: {subtitle_color}")

    # Fallback for auto colors when not using image background
    if wave_color == 'auto':
        wave_color = '#00ff88'
    if subtitle_color == 'auto':
        subtitle_color = '#ffffff'

    # Handle intro clip settings
    intro_font_path = intro_font if intro_font else str(DEFAULT_INTRO_FONT)
    if intro_title:
        click.echo(f"Intro clip: {intro_clip_duration}s with title")
        if intro_bg:
            click.echo(f"Intro background: {Path(intro_bg).name}")

        # Auto detect intro title color based on intro background
        if intro_title_color == 'auto':
            from .backgrounds import get_background, calculate_auto_title_color
            if intro_bg and intro_bg.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v')):
                # Video background - default to white (most videos are dark)
                intro_title_color = '#ffffff'
            elif intro_bg:
                # Static image intro background - calculate auto color
                intro_bg_img = get_background(width, height, 'image', intro_bg)
                intro_title_color = calculate_auto_title_color(intro_bg_img)
            elif bg_type == 'image':
                # Use main background for auto color
                if temp_bg is None:
                    temp_bg = get_background(width, height, bg_type, bg_value)
                intro_title_color = calculate_auto_title_color(temp_bg)
            else:
                # Default to white for dark backgrounds
                intro_title_color = '#ffffff'
            click.echo(f"Auto intro title color: {intro_title_color}")

    # Log background music if provided
    if bg_music:
        click.echo(f"Background music: {Path(bg_music).name} at {bg_music_volume}%")

    click.echo(f"Input: {input_audio}")
    click.echo(f"Output: {output_video}")
    click.echo(f"Style: {style}, Resolution: {width}x{height}, FPS: {fps}")
    if volume != 100:
        click.echo(f"Volume: {volume}%")

    def progress(msg):
        click.echo(msg)

    # Transcribe if subtitles enabled
    subtitles = None
    if subtitle:
        from .transcribe import transcribe_audio, tokens_to_subtitles
        click.echo("Transcribing audio...")
        tokens = transcribe_audio(input_audio, progress_callback=progress)
        # Parse replacements from file and command line
        replace_dict = {}
        if replace_file:
            with open(replace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        old, new = line.split('=', 1)
                        replace_dict[old] = new
        # Command line replacements override file
        for r in replacements:
            if '=' in r:
                old, new = r.split('=', 1)
                replace_dict[old] = new
        subtitles = tokens_to_subtitles(tokens, replacements=replace_dict)
        click.echo(f"Generated {len(subtitles)} subtitle segments")

    # Log performance settings if non-default
    if preset != 'ultrafast':
        click.echo(f"Encoding preset: {preset}")
    if threads > 0:
        click.echo(f"Threads: {threads}")

    import time
    start_time = time.time()

    if audio_only:
        # Audio-only mode
        output_file = output_video
        if not output_file.lower().endswith(('.mp3', '.m4a', '.aac', '.wav')):
            output_file = output_file.rsplit('.', 1)[0] + '.m4a'
        click.echo(f"Audio-only mode: {output_file}")

        success, audio_duration = render_audio(
            input_audio=input_audio,
            output_audio=output_file,
            volume=volume,
            intro_sound=intro_sound,
            intro_duration=intro_duration,
            outro_sound=outro_sound,
            intro_clip_duration=intro_clip_duration if intro_title else 0,
            bg_music=bg_music,
            bg_music_volume=bg_music_volume,
            end_screen_duration=end_screen_duration if end_screen or outro_sound else 0,
            progress_callback=progress
        )

        elapsed = time.time() - start_time

        if success:
            click.echo(f"Audio saved to {output_file}")
            elapsed_min = int(elapsed // 60)
            elapsed_sec = elapsed % 60
            audio_min = int(audio_duration // 60)
            audio_sec = audio_duration % 60
            ratio = elapsed / audio_duration if audio_duration > 0 else 0
            click.echo(f"Time: {elapsed_min}m {elapsed_sec:.1f}s / Audio: {audio_min}m {audio_sec:.1f}s (ratio: {ratio:.2f}x)")
        else:
            click.echo("Error generating audio", err=True)
            raise SystemExit(1)
    else:
        # Video mode
        success, video_duration = render_video(
            input_audio=input_audio,
            output_video=output_video,
            style=style,
            bg_type=bg_type,
            bg_value=bg_value,
            wave_color=wave_color,
            width=width,
            height=height,
            fps=fps,
            avatar_path=avatar_path,
            avatar_size=avatar_size,
            subtitles=subtitles,
            subtitle_font_size=subtitle_font_size,
            subtitle_color=subtitle_color,
            volume=volume,
            intro_sound=intro_sound,
            intro_duration=intro_duration,
            outro_sound=outro_sound,
            intro_title=intro_title,
            intro_subtitle=intro_subtitle,
            intro_static=intro_static,
            intro_avatar=avatar_path if intro_static else None,
            intro_bg=intro_bg,
            intro_font=intro_font_path,
            intro_title_color=intro_title_color,
            intro_clip_duration=intro_clip_duration,
            bg_music=bg_music,
            bg_music_volume=bg_music_volume,
            thumbnail=thumbnail,
            end_screen=end_screen if end_screen is not None else (outro_sound is not None),
            end_screen_duration=end_screen_duration,
            preset=preset,
            threads=threads,
            wave_sync=wave_sync,
            progress_callback=progress
        )

        elapsed = time.time() - start_time

        if success:
            click.echo(f"Video saved to {output_video}")
            elapsed_min = int(elapsed // 60)
            elapsed_sec = elapsed % 60
            video_min = int(video_duration // 60)
            video_sec = video_duration % 60
            ratio = elapsed / video_duration if video_duration > 0 else 0
            click.echo(f"Time: {elapsed_min}m {elapsed_sec:.1f}s / Video: {video_min}m {video_sec:.1f}s (ratio: {ratio:.2f}x)")
        else:
            click.echo("Error generating video", err=True)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
