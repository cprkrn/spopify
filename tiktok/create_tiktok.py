#!/usr/bin/env python3
"""
TikTok Video Generator for SoundCloud to Spotify Converter

Creates a vertical (9:16) explainer video automatically.
"""

import os
import sys
from pathlib import Path

# MoviePy 2.x imports
from moviepy import (
    VideoClip, TextClip, CompositeVideoClip, ColorClip,
    concatenate_videoclips, VideoFileClip
)
from moviepy.video.fx import FadeIn, FadeOut

import numpy as np

# TikTok dimensions (9:16 vertical)
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Color scheme - dark theme with neon accents
BG_COLOR = (15, 15, 25)  # Dark navy
ACCENT_COLOR = (30, 215, 96)  # Spotify green
CODE_BG = (30, 30, 45)

# Font paths for macOS
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
FONT_REGULAR = "/System/Library/Fonts/Helvetica.ttc"
FONT_MONO = "/System/Library/Fonts/Menlo.ttc"


def create_text_slide(text, subtext="", duration=3, font_size=70, emoji=""):
    """Create a text slide with animation."""
    clips = []
    
    # Background
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    # Main text with emoji
    display_text = f"{emoji} {text}" if emoji else text
    main_text = TextClip(
        text=display_text,
        font_size=font_size,
        color='white',
        font=FONT_BOLD,
        size=(WIDTH - 100, None),
        method='caption',
        text_align='center',
        duration=duration
    ).with_position(('center', HEIGHT // 2 - 100))
    clips.append(main_text)
    
    # Subtext
    if subtext:
        sub = TextClip(
            text=subtext,
            font_size=40,
            color='rgb(180, 180, 200)',
            font=FONT_REGULAR,
            size=(WIDTH - 120, None),
            method='caption',
            text_align='center',
            duration=duration
        ).with_position(('center', HEIGHT // 2 + 50))
        clips.append(sub)
    
    return CompositeVideoClip(clips)


def create_code_slide(code_lines, title="", duration=4):
    """Create a slide showing code."""
    clips = []
    
    # Background
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    # Title
    if title:
        title_clip = TextClip(
            text=title,
            font_size=50,
            color='white',
            font=FONT_BOLD,
            duration=duration
        ).with_position(('center', 200))
        clips.append(title_clip)
    
    # Code background box
    code_bg = ColorClip(
        size=(WIDTH - 80, len(code_lines) * 50 + 60),
        color=CODE_BG,
        duration=duration
    ).with_position(('center', 350))
    clips.append(code_bg)
    
    # Code lines
    y_start = 380
    for i, line in enumerate(code_lines):
        code_text = TextClip(
            text=line,
            font_size=32,
            color='rgb(30, 215, 96)',  # Spotify green for code
            font=FONT_MONO,
            duration=duration
        ).with_position((80, y_start + i * 50))
        clips.append(code_text)
    
    return CompositeVideoClip(clips)


def create_step_slide(step_num, total_steps, title, description, duration=3):
    """Create a numbered step slide."""
    clips = []
    
    # Background
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    # Step indicator
    step_text = TextClip(
        text=f"Step {step_num}/{total_steps}",
        font_size=35,
        color='rgb(30, 215, 96)',
        font=FONT_BOLD,
        duration=duration
    ).with_position(('center', 400))
    clips.append(step_text)
    
    # Title
    title_clip = TextClip(
        text=title,
        font_size=65,
        color='white',
        font=FONT_BOLD,
        size=(WIDTH - 100, None),
        method='caption',
        text_align='center',
        duration=duration
    ).with_position(('center', 500))
    clips.append(title_clip)
    
    # Description
    desc_clip = TextClip(
        text=description,
        font_size=38,
        color='rgb(200, 200, 220)',
        font=FONT_REGULAR,
        size=(WIDTH - 120, None),
        method='caption',
        text_align='center',
        duration=duration
    ).with_position(('center', 700))
    clips.append(desc_clip)
    
    return CompositeVideoClip(clips)


def create_intro_slide(duration=3):
    """Create the intro/hook slide."""
    clips = []
    
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    # Hook text
    hook = TextClip(
        text="I built a tool that\nautomatically converts\nSoundCloud mixes to\nSpotify playlists",
        font_size=60,
        color='white',
        font=FONT_BOLD,
        size=(WIDTH - 100, None),
        method='caption',
        text_align='center',
        duration=duration
    ).with_position(('center', 'center'))
    clips.append(hook)
    
    return CompositeVideoClip(clips)


def create_tech_slide(duration=3):
    """Create the tech stack slide."""
    clips = []
    
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    title = TextClip(
        text="Built with",
        font_size=45,
        color='rgb(150, 150, 170)',
        font=FONT_REGULAR,
        duration=duration
    ).with_position(('center', 400))
    clips.append(title)
    
    techs = ["Python", "Shazam API", "Spotify API", "yt-dlp"]
    y_start = 500
    for i, tech in enumerate(techs):
        tech_text = TextClip(
            text=tech,
            font_size=55,
            color='rgb(30, 215, 96)',
            font=FONT_BOLD,
            duration=duration
        ).with_position(('center', y_start + i * 80))
        clips.append(tech_text)
    
    return CompositeVideoClip(clips)


def create_outro_slide(duration=3):
    """Create the outro/CTA slide."""
    clips = []
    
    bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=duration)
    clips.append(bg)
    
    cta = TextClip(
        text="Link in bio\nfor the code",
        font_size=70,
        color='white',
        font=FONT_BOLD,
        size=(WIDTH - 100, None),
        method='caption',
        text_align='center',
        duration=duration
    ).with_position(('center', HEIGHT // 2 - 100))
    clips.append(cta)
    
    sub = TextClip(
        text="github.com/yourusername/scf",
        font_size=35,
        color='rgb(30, 215, 96)',
        font=FONT_REGULAR,
        duration=duration
    ).with_position(('center', HEIGHT // 2 + 100))
    clips.append(sub)
    
    return CompositeVideoClip(clips)


def add_screen_recording(video_path, duration=5):
    """Include an existing screen recording, cropped/fitted for vertical."""
    try:
        clip = VideoFileClip(video_path)
        
        # Calculate scaling to fit width while maintaining aspect ratio
        scale = WIDTH / clip.w
        new_height = int(clip.h * scale)
        
        clip = clip.resized(width=WIDTH)
        
        # If taller than screen, crop from center
        if new_height > HEIGHT:
            clip = clip.cropped(y_center=new_height // 2, height=HEIGHT)
        
        # Trim to duration
        if clip.duration > duration:
            clip = clip.subclipped(0, duration)
        
        # Center vertically
        bg = ColorClip(size=(WIDTH, HEIGHT), color=BG_COLOR, duration=clip.duration)
        final = CompositeVideoClip([
            bg,
            clip.with_position(('center', 'center'))
        ])
        
        return final
    except Exception as e:
        print(f"⚠️ Could not load video {video_path}: {e}")
        return None


def generate_tiktok_video(output_path="tiktok_explainer.mp4", include_recording=None):
    """Generate the full TikTok video."""
    print("🎬 Generating TikTok video...")
    
    slides = []
    
    # 1. Intro/Hook (3s)
    print("  Creating intro...")
    slides.append(create_intro_slide(duration=3))
    
    # 2. The Problem (2.5s)
    print("  Creating problem slide...")
    slides.append(create_text_slide(
        "The Problem",
        "Found an amazing DJ mix on SoundCloud\nbut wanted the songs on Spotify",
        duration=2.5,
        emoji="🤔"
    ))
    
    # 3. Step 1 - Download (2.5s)
    print("  Creating step slides...")
    slides.append(create_step_slide(
        1, 3,
        "Download Audio",
        "yt-dlp grabs the audio\nfrom any SoundCloud URL",
        duration=2.5
    ))
    
    # 4. Step 2 - Identify (3s)
    slides.append(create_step_slide(
        2, 3,
        "Identify Songs",
        "Shazam analyzes 20-second\nsegments to find each track",
        duration=3
    ))
    
    # 5. Step 3 - Create Playlist (2.5s)
    slides.append(create_step_slide(
        3, 3,
        "Create Playlist",
        "Searches Spotify and adds\nall found tracks automatically",
        duration=2.5
    ))
    
    # 6. Optional: Include screen recording
    if include_recording and os.path.exists(include_recording):
        print(f"  Adding screen recording from {include_recording}...")
        recording = add_screen_recording(include_recording, duration=6)
        if recording:
            slides.append(recording)
    
    # 7. Code snippet (3s)
    print("  Creating code slide...")
    slides.append(create_code_slide([
        "python soundcloud_to_spotify.py \\",
        '  "soundcloud.com/dj/mix" \\',
        '  --name "My Playlist"'
    ], title="One command:", duration=3))
    
    # 8. Tech stack (2.5s)
    print("  Creating tech stack slide...")
    slides.append(create_tech_slide(duration=2.5))
    
    # 9. Result (2.5s)
    slides.append(create_text_slide(
        "Result",
        "18 tracks identified and added\nto Spotify in under 2 minutes",
        duration=2.5,
        emoji="✨"
    ))
    
    # 10. Outro/CTA (3s)
    print("  Creating outro...")
    slides.append(create_outro_slide(duration=3))
    
    # Combine all slides with transitions
    print("  Combining slides...")
    
    # Add fade transitions
    processed_slides = []
    for i, slide in enumerate(slides):
        if i == 0:
            slide = slide.with_effects([FadeIn(0.3)])
        if i == len(slides) - 1:
            slide = slide.with_effects([FadeOut(0.5)])
        processed_slides.append(slide)
    
    final_video = concatenate_videoclips(processed_slides, method="compose")
    
    # Write output
    print(f"  Rendering to {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio=False,  # No audio by default, add your own music!
        preset='medium',
        threads=4
    )
    
    print(f"\n✅ TikTok video created: {output_path}")
    print(f"   Duration: {final_video.duration:.1f}s")
    print(f"   Resolution: {WIDTH}x{HEIGHT}")
    print("\n💡 Tips:")
    print("   - Add trending audio in TikTok/CapCut")
    print("   - Upload to TikTok, Reels, or Shorts")
    print("   - Use #coding #python #spotify #soundcloud hashtags")
    
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate a TikTok explainer video")
    parser.add_argument(
        "--output", "-o",
        default="tiktok_explainer.mp4",
        help="Output video path (default: tiktok_explainer.mp4)"
    )
    parser.add_argument(
        "--recording", "-r",
        help="Path to a screen recording to include (optional)"
    )
    
    args = parser.parse_args()
    
    generate_tiktok_video(
        output_path=args.output,
        include_recording=args.recording
    )
