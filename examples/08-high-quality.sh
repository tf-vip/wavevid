#!/bin/bash
# High quality export with slower encoding

wavevid audio.m4a -o hq_output.mp4 \
  --aspect 16:9 \
  --style spectrum \
  --bg random \
  --avatar avatar.jpg \
  --preset slow \
  --fps 60 \
  --threads 8
