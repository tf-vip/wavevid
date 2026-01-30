#!/bin/bash
# Subtitles with text replacements to fix transcription errors

# Create replacements file
cat > replacements.txt << 'EOF'
AI=A.I.
gonna=going to
wanna=want to
# Lines starting with # are ignored
EOF

wavevid audio.m4a -o output.mp4 \
  --aspect 1:1 \
  --avatar avatar.jpg \
  --subtitle \
  --replace-file replacements.txt \
  --replace "MyBrand=My Brand"
