#!/bin/bash
# Audio mix only (no video) - useful for preparing audio with intro/outro

wavevid podcast.m4a -o mixed.m4a \
  --audio-only \
  --intro intro.wav \
  --intro-duration 3 \
  --outro outro.wav \
  --bg-music background.mp3 \
  --bg-music-volume 15 \
  --volume 120
