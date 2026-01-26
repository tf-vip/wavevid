# WaveVid Improvements

## Audio Features

### Volume Control (`--volume`)
Adjust audio volume as percentage. Default 100%.
```bash
--volume 120  # 120% volume boost
```

### Intro/Outro Sound (`--intro`, `--outro`)
Add background music with smart crossfade mixing.

**Intro behavior:**
- FadeIn: 0.5s
- Play: 5s
- FadeOut: 10s (overlaps with main audio start)
- Volume: 60% (lower than main)

**Outro behavior:**
- Starts 10s before main audio ends
- FadeIn: 10s (overlaps with main audio end)
- Play: 5s after main
- FadeOut: 0.5s
- Volume: 60%

**Audio normalization:**
- All sources normalized with `loudnorm` filter (-16 LUFS)
- Main audio fades in 3s for smooth transition with intro
- Prevents intro from drowning out speech

```bash
--intro sounds/intro.wav --outro sounds/outro.wav
```

## Visual Features

### Auto Wave Color (`--wave-color auto`)
Automatically calculates optimal waveform color based on background.

**Algorithm:**
1. Sample center 40% of background (where visualizer appears)
2. K-means clustering extracts 3 dominant colors
3. Calculate center region luminance
4. Pick color with best contrast + saturation score
5. Boost saturation to 70%+ for visibility
6. Adjust brightness based on background luminance

### Auto Subtitle Color (`--subtitle-color auto`)
Calculates optimal subtitle text color.

**Algorithm:**
1. Sample bottom 20% of background (where subtitles appear)
2. Calculate average luminance
3. Return white (`#ffffff`) for dark backgrounds
4. Return near-black (`#1a1a1a`) for light backgrounds

### Background Aspect Ratio Fix
Images now use center-crop instead of stretch to preserve aspect ratio.

**Before:** Distorted images when aspect ratio differs from video
**After:** Clean center-crop, no distortion

### Dynamic Background Discovery
Random background mode now dynamically scans for all image files:
- Supports: jpg, jpeg, png, webp
- Scans subdirectories
- No hardcoded file list

## Subtitle Features

### Text Replacement (`--replace`)
Replace words in transcription output. Useful for fixing common ASR mistakes.

```bash
--replace "Cloud=Claude" --replace "Galaxy=Perplexity"
```

Multiple replacements supported. Applied after subtitle segments are joined.

## Performance Optimizations

### FFmpeg Encoding
- Changed preset from `medium` to `ultrafast`
- Added `-tune animation` for generated content
- Result: ~2-3x faster encoding

### Frame Rendering
- Pre-computed subtitle lookup table (O(1) vs O(n) per frame)
- Pre-computed avatar position
- Reduced progress reporting frequency (every 2s vs 1s)
- Minimized image mode conversions

### Parallel Processing
Multiple videos can be rendered simultaneously:
```bash
wavevid audio.mp3 --bg image --bg-value bg1.jpg -o out1.mp4 &
wavevid audio.mp3 --bg image --bg-value bg2.jpg -o out2.mp4 &
wavevid audio.mp3 --bg image --bg-value bg3.jpg -o out3.mp4 &
wait
```

## CLI Options Summary

| Option | Description | Default |
|--------|-------------|---------|
| `--volume` | Audio volume % | 100 |
| `--intro` | Intro sound file | None |
| `--outro` | Outro sound file | None |
| `--wave-color` | Wave color (hex or "auto") | #00ff88 |
| `--subtitle-color` | Subtitle color (hex or "auto") | auto |
| `--replace` | Text replacement (old=new) | None |
| `--bg random` | Random background from folder | - |

## Example Command

```bash
wavevid audio.m4a \
  --style radial \
  --bg image --bg-value backgrounds/bg9.jpg \
  --wave-color auto \
  --width 1080 --height 1080 \
  --avatar avatar.jpg \
  --subtitle --subtitle-color auto \
  --volume 120 \
  --replace "Cloud=Claude" \
  --intro sounds/intro.wav \
  --outro sounds/outro.wav \
  -o output.mp4
```
