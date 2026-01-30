#!/bin/bash
# YouTube landscape format (16:9)

wavevid audio.m4a -o youtube.mp4 \
  --aspect 16:9 \
  --style waveform \
  --bg image \
  --bg-value background.jpg \
  --wave-color "#00ff88" \
  --avatar avatar.jpg
