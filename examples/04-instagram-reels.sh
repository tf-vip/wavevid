#!/bin/bash
# Instagram Reels / TikTok format (9:16 vertical)

wavevid audio.m4a -o reel.mp4 \
  --aspect 9:16 \
  --style bars \
  --bg gradient \
  --bg-value "#667eea,#764ba2" \
  --avatar avatar.jpg
