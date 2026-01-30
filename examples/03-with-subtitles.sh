#!/bin/bash
# Video with auto-generated subtitles
# Requires: SONIOX_API_KEY in .env

wavevid audio.m4a -o output.mp4 \
  --aspect 1:1 \
  --avatar avatar.jpg \
  --style radial \
  --bg random \
  --wave-color auto \
  --subtitle \
  --subtitle-color auto
