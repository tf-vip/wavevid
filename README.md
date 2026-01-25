# wavevid

Audio to waveform video generator with avatar overlay and auto-transcribed subtitles.

## Install

```bash
pip install -e .
```

**Requirements:** FFmpeg must be installed (`brew install ffmpeg` on macOS).

## Usage

```bash
wavevid input.m4a -o output.mp4 [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | output.mp4 | Output video file |
| `--style` | waveform | Visualization: `waveform`, `radial`, `bars` |
| `--bg` | color | Background: `color`, `gradient`, `image`, `random` |
| `--bg-value` | #1a1a2e | Hex color, "color1,color2" for gradient, or image path |
| `--wave-color` | #00ff88 | Wave/bar color (hex) |
| `--width` | 1920 | Video width |
| `--height` | 1080 | Video height |
| `--fps` | 30 | Frames per second |
| `--avatar` | - | Avatar image path (centered, circular) |
| `--avatar-size` | auto | Avatar size in pixels |
| `--subtitle` | off | Enable Soniox transcription |
| `--subtitle-font-size` | auto | Font size for subtitles |
| `--subtitle-color` | #ffffff | Subtitle text color |

## Examples

### Basic waveform
```bash
wavevid audio.m4a -o video.mp4
```

### Radial with avatar (Facebook 1:1)
```bash
wavevid audio.m4a -o video.mp4 \
  --style radial \
  --avatar avatar.jpg \
  --width 1080 --height 1080
```

### Random background + subtitles
```bash
wavevid audio.m4a -o video.mp4 \
  --style bars \
  --bg random \
  --avatar avatar.jpg \
  --subtitle \
  --width 1080 --height 1080
```

### Gradient background
```bash
wavevid audio.m4a -o video.mp4 \
  --bg gradient \
  --bg-value "#1a1a2e,#4a0e4e"
```

## Subtitles

Subtitles use [Soniox API](https://soniox.com) for transcription.

1. Get API key from https://console.soniox.com
2. Create `.env` file:
   ```
   SONIOX_API_KEY=your_key_here
   ```
3. Run with `--subtitle` flag

Transcripts are cached in `.transcribe_cache/` to avoid repeated API calls.

## Facebook Video Specs

| Placement | Ratio | Resolution |
|-----------|-------|------------|
| Feed | 1:1 or 4:5 | 1080x1080 or 1080x1350 |
| Reels/Stories | 9:16 | 1080x1920 |

## Adding Backgrounds

Add `.jpg` or `.png` files to `wavevid/backgrounds/` for use with `--bg random`.

## Structure

```
wavevid/
├── __init__.py
├── cli.py           # CLI entry point
├── audio.py         # Audio analysis (librosa)
├── backgrounds.py   # Background generators
├── renderer.py      # Frame generation + FFmpeg
├── transcribe.py    # Soniox API + caching
├── backgrounds/     # Default background images
└── visualizers/
    ├── base.py      # Base class
    ├── waveform.py  # Horizontal wave
    ├── radial.py    # Circular bars
    └── bars.py      # Equalizer bars
```
