#!/bin/bash
# Simple TikTok video creator using FFmpeg
# Creates a vertical video with text slides explaining the tool

OUTPUT="${1:-tiktok_simple.mp4}"
WIDTH=1080
HEIGHT=1920
FPS=30
DURATION_PER_SLIDE=3

# Colors
BG_COLOR="0x19191f"
TEXT_COLOR="white"
ACCENT_COLOR="0x1ed760"

echo "🎬 Creating TikTok video with FFmpeg..."

# Create temp directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Slide content
SLIDES=(
    "I built a tool that converts SoundCloud mixes to Spotify playlists"
    "Step 1: Download audio from SoundCloud using yt-dlp"
    "Step 2: Identify songs using Shazam API (20s segments)"
    "Step 3: Create Spotify playlist automatically"
    "One command: python soundcloud_to_spotify.py URL"
    "Built with: Python + Shazam + Spotify API"
    "Link in bio for the code!"
)

# Create slides
slide_num=0
for text in "${SLIDES[@]}"; do
    slide_num=$((slide_num + 1))
    slide_file="$TEMP_DIR/slide_${slide_num}.mp4"
    
    echo "  Creating slide $slide_num: ${text:0:40}..."
    
    # Create a slide with text overlay using FFmpeg
    ffmpeg -y -f lavfi -i "color=c=$BG_COLOR:s=${WIDTH}x${HEIGHT}:d=$DURATION_PER_SLIDE:r=$FPS" \
        -vf "drawtext=text='${text}':fontcolor=white:fontsize=55:x=(w-text_w)/2:y=(h-text_h)/2:font=Helvetica" \
        -c:v libx264 -pix_fmt yuv420p -preset fast \
        "$slide_file" 2>/dev/null
done

# Create file list for concatenation
echo "  Concatenating slides..."
FILELIST="$TEMP_DIR/filelist.txt"
for i in $(seq 1 $slide_num); do
    echo "file 'slide_${i}.mp4'" >> "$FILELIST"
done

# Concatenate all slides
ffmpeg -y -f concat -safe 0 -i "$FILELIST" \
    -c:v libx264 -pix_fmt yuv420p -preset medium \
    "$OUTPUT" 2>/dev/null

echo ""
echo "✅ Created: $OUTPUT"
echo "   Duration: $((slide_num * DURATION_PER_SLIDE))s"
echo "   Resolution: ${WIDTH}x${HEIGHT}"
echo ""
echo "💡 Tips:"
echo "   - Add trending audio in TikTok/CapCut"
echo "   - For fancier videos, use: python create_tiktok.py"

