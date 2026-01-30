#!/bin/bash
# Full podcast video with intro, outro, background music, and subtitles

wavevid podcast.m4a -o podcast.mp4 \
  --aspect 1:1 \
  --style radial \
  --bg random \
  --wave-color auto \
  --avatar host.jpg \
  --subtitle \
  --subtitle-color auto \
  --intro intro.wav \
  --intro-duration 3 \
  --intro-title "My Podcast" \
  --intro-subtitle "Episode 1" \
  --intro-clip-duration 4 \
  --outro outro.wav \
  --bg-music lofi.mp3 \
  --bg-music-volume 10 \
  --end-screen \
  --end-screen-duration 5 \
  --thumbnail thumbnail.jpg
