"""CLI entry point for wavevid."""
import click
import random
from pathlib import Path
from .renderer import render_video

# Default backgrounds directory (inside package)
BACKGROUNDS_DIR = Path(__file__).parent / 'backgrounds'


@click.command()
@click.argument('input_audio', type=click.Path(exists=True))
@click.option('-o', '--output', 'output_video', default='output.mp4', help='Output video file')
@click.option('--style', type=click.Choice(['waveform', 'radial', 'bars']), default='waveform', help='Visualization style')
@click.option('--bg', 'bg_type', type=click.Choice(['color', 'gradient', 'image', 'random']), default='color', help='Background type (random picks from backgrounds/)')
@click.option('--bg-value', default='#1a1a2e', help='Background value: hex color, "color1,color2" for gradient, or image path')
@click.option('--wave-color', default='#00ff88', help='Wave/bar color (hex)')
@click.option('--width', default=1920, help='Video width')
@click.option('--height', default=1080, help='Video height')
@click.option('--fps', default=30, help='Frames per second')
@click.option('--avatar', 'avatar_path', type=click.Path(exists=True), help='Avatar image to place at center')
@click.option('--avatar-size', type=int, help='Avatar size in pixels (default: 1/4 of min dimension)')
@click.option('--subtitle/--no-subtitle', default=False, help='Enable subtitle transcription via Soniox')
@click.option('--subtitle-font-size', type=int, help='Subtitle font size (default: height/20)')
@click.option('--subtitle-color', default='#ffffff', help='Subtitle text color (hex)')
def main(input_audio, output_video, style, bg_type, bg_value, wave_color, width, height, fps, avatar_path, avatar_size, subtitle, subtitle_font_size, subtitle_color):
    """Generate waveform video from audio file."""
    # Handle random background selection
    if bg_type == 'random':
        bg_files = list(BACKGROUNDS_DIR.glob('*.jpg')) + list(BACKGROUNDS_DIR.glob('*.png'))
        if bg_files:
            bg_value = str(random.choice(bg_files))
            bg_type = 'image'
            click.echo(f"Random background: {Path(bg_value).name}")
        else:
            click.echo("No backgrounds found, using default color")
            bg_type = 'color'
            bg_value = '#1a1a2e'

    click.echo(f"Input: {input_audio}")
    click.echo(f"Output: {output_video}")
    click.echo(f"Style: {style}, Resolution: {width}x{height}, FPS: {fps}")

    def progress(msg):
        click.echo(msg)

    # Transcribe if subtitles enabled
    subtitles = None
    if subtitle:
        from .transcribe import transcribe_audio, tokens_to_subtitles
        click.echo("Transcribing audio...")
        tokens = transcribe_audio(input_audio, progress_callback=progress)
        subtitles = tokens_to_subtitles(tokens)
        click.echo(f"Generated {len(subtitles)} subtitle segments")

    success = render_video(
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
        progress_callback=progress
    )

    if success:
        click.echo(f"Video saved to {output_video}")
    else:
        click.echo("Error generating video", err=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
