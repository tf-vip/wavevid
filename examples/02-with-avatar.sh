#!/bin/bash
# Square video with avatar for social media

wavevid audio.m4a -o output.mp4 \
  --aspect 1:1 \
  --avatar avatar.jpg \
  --style radial \
  --bg random \
  --wave-color auto
