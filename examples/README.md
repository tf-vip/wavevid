# Wavevid Examples

Example scripts for common use cases.

## Quick Start

```bash
# Make scripts executable
chmod +x *.sh

# Run any example (replace filenames with your own)
./01-basic.sh
```

## Examples

| Script | Description |
|--------|-------------|
| `01-basic.sh` | Simplest usage - just audio to video |
| `02-with-avatar.sh` | Square video with avatar for social media |
| `03-with-subtitles.sh` | Auto-generated subtitles (requires Soniox API) |
| `04-instagram-reels.sh` | Vertical 9:16 for Reels/TikTok |
| `05-youtube-landscape.sh` | Horizontal 16:9 for YouTube |
| `06-podcast-full.sh` | Full podcast with intro, outro, music, subtitles |
| `07-audio-only.sh` | Mix audio without rendering video |
| `08-high-quality.sh` | Slow encode for better quality |
| `09-custom-colors.sh` | Custom gradient and wave colors |
| `10-text-replacements.sh` | Fix subtitle transcription errors |

## Tips

- Use `--bg random` to pick a random bundled background
- Use `--wave-color auto` to auto-detect color from background
- Use `--aspect` presets: `16:9`, `9:16`, `1:1`, `4:5`
- Add `--thumbnail output.jpg` to save a thumbnail image
