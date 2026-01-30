#!/bin/bash
# Custom gradient background with specific colors

wavevid audio.m4a -o custom.mp4 \
  --aspect 1:1 \
  --style bars \
  --bg gradient \
  --bg-value "#1a1a2e,#4a0e4e" \
  --wave-color "#ff6b6b" \
  --avatar avatar.jpg \
  --subtitle \
  --subtitle-color "#ffffff"
