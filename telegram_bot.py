#!/usr/bin/env python3
"""
Telegram Bot for SoundCloud to Spotify Converter

Send a SoundCloud URL and get a Spotify playlist back!
"""

import asyncio
import os
import re
import tempfile
import subprocess
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Import our converter components
from pydub import AudioSegment
from shazamio import Shazam
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

# Regex to match SoundCloud URLs
SOUNDCLOUD_REGEX = re.compile(
    r'https?://(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+(?:/[\w-]+)?'
)

# Store for tracking active jobs
active_jobs: dict[int, bool] = {}


class SpotifyPlaylistCreator:
    """Handles Spotify playlist creation."""
    
    def __init__(self):
        self.spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="playlist-modify-public playlist-modify-private",
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")
        ))
    
    def search_track(self, title: str, artist: str) -> str | None:
        """Search for a track on Spotify."""
        query = f"track:{title} artist:{artist}"
        try:
            results = self.spotify.search(q=query, type="track", limit=1)
            if results["tracks"]["items"]:
                return results["tracks"]["items"][0]["uri"]
            
            # Fallback: relaxed search
            query = f"{artist} {title}"
            results = self.spotify.search(q=query, type="track", limit=1)
            if results["tracks"]["items"]:
                return results["tracks"]["items"][0]["uri"]
        except Exception:
            pass
        return None
    
    def create_playlist(self, tracks: list[dict], name: str, description: str = "") -> tuple[str, int, int]:
        """
        Create a Spotify playlist from identified tracks.
        
        Returns: (playlist_url, tracks_added, tracks_not_found)
        """
        user = self.spotify.current_user()
        user_id = user["id"]
        
        # Create playlist
        playlist = self.spotify.user_playlist_create(
            user=user_id,
            name=f"[SCF] {name}",
            public=True,
            description=description or f"Created by SoundCloud to Spotify Bot"
        )
        playlist_id = playlist["id"]
        playlist_url = playlist["external_urls"]["spotify"]
        
        # Find and add tracks
        spotify_uris = []
        not_found = 0
        
        for track in tracks:
            uri = self.search_track(track["title"], track["artist"])
            if uri:
                spotify_uris.append(uri)
            else:
                not_found += 1
        
        # Add tracks in batches
        if spotify_uris:
            for i in range(0, len(spotify_uris), 100):
                batch = spotify_uris[i:i + 100]
                self.spotify.playlist_add_items(playlist_id, batch)
        
        return playlist_url, len(spotify_uris), not_found


async def identify_tracks(audio_path: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> list[dict]:
    """Identify tracks in an audio file using Shazam."""
    
    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    duration_sec = duration_ms // 1000
    
    segment_duration = 20 * 1000  # 20 seconds
    segment_step = 45 * 1000  # 45 seconds between segments
    
    await update.message.reply_text(
        f"⏱️ Duration: {duration_sec // 60}m {duration_sec % 60}s\n"
        f"🔍 Analyzing... (this may take {duration_sec // 60 + 1} minutes)"
    )
    
    identified_tracks = []
    seen_tracks = set()
    
    position = 0
    last_update = 0
    request_count = 0
    
    while position + segment_duration <= duration_ms:
        timestamp_sec = position // 1000
        progress_pct = (position / duration_ms) * 100
        
        # Send progress update every 20%
        if int(progress_pct // 20) > last_update:
            last_update = int(progress_pct // 20)
            await update.message.reply_text(
                f"📊 Progress: {progress_pct:.0f}% ({len(identified_tracks)} tracks found)"
            )
        
        # Rate limiting
        request_count += 1
        if request_count > 1:
            await asyncio.sleep(2)
        
        segment = audio[position:position + segment_duration]
        
        # Export segment
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            segment.export(tmp.name, format="mp3", bitrate="128k")
            tmp_path = tmp.name
        
        try:
            for attempt in range(3):
                try:
                    shazam = Shazam()
                    result = await asyncio.wait_for(
                        shazam.recognize(tmp_path),
                        timeout=15.0
                    )
                    
                    if result and "track" in result:
                        track_data = result["track"]
                        title = track_data.get("title", "Unknown")
                        artist = track_data.get("subtitle", "Unknown")
                        track_key = (title.lower(), artist.lower())
                        
                        if track_key not in seen_tracks:
                            seen_tracks.add(track_key)
                            identified_tracks.append({
                                "title": title,
                                "artist": artist,
                                "timestamp_seconds": timestamp_sec
                            })
                    break
                    
                except asyncio.TimeoutError:
                    if attempt < 2:
                        await asyncio.sleep(3)
        finally:
            os.unlink(tmp_path)
        
        position += segment_step
    
    return identified_tracks


async def download_audio(url: str, output_dir: str) -> str:
    """Download audio from SoundCloud."""
    output_template = os.path.join(output_dir, "audio.%(ext)s")
    
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_template,
        url
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    # Find downloaded file
    for ext in ["mp3", "m4a", "wav", "ogg"]:
        path = os.path.join(output_dir, f"audio.{ext}")
        if os.path.exists(path):
            return path
    
    raise RuntimeError("Failed to download audio")


async def process_soundcloud_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    """Process a SoundCloud URL and create a Spotify playlist."""
    user_id = update.effective_user.id
    
    # Check if user already has an active job
    if active_jobs.get(user_id):
        await update.message.reply_text(
            "⏳ You already have a mix being processed. Please wait for it to finish!"
        )
        return
    
    active_jobs[user_id] = True
    
    try:
        await update.message.reply_text(
            f"🎵 Got it! Processing your SoundCloud mix...\n\n"
            f"📥 Downloading audio..."
        )
        
        # Extract a name from the URL
        url_parts = url.rstrip('/').split('/')
        mix_name = url_parts[-1].replace('-', ' ').title()
        if len(url_parts) >= 2:
            artist_name = url_parts[-2].replace('-', ' ').title()
            mix_name = f"{artist_name} - {mix_name}"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Download
            audio_path = await download_audio(url, tmp_dir)
            await update.message.reply_text("✅ Downloaded! Starting analysis...")
            
            # Identify tracks
            tracks = await identify_tracks(audio_path, update, context)
            
            if not tracks:
                await update.message.reply_text(
                    "😕 Couldn't identify any tracks in this mix.\n"
                    "This might happen with very obscure/unreleased music."
                )
                return
            
            await update.message.reply_text(
                f"🎉 Found {len(tracks)} tracks!\n"
                f"🎧 Creating Spotify playlist..."
            )
            
            # Save tracklist
            tracklist_dir = Path("tracklists")
            tracklist_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = re.sub(r'[^\w\-]', '_', mix_name)[:50]
            tracklist_path = tracklist_dir / f"{safe_name}_{timestamp}.json"
            
            with open(tracklist_path, "w") as f:
                json.dump({
                    "source_url": url,
                    "mix_name": mix_name,
                    "track_count": len(tracks),
                    "created_at": datetime.now().isoformat(),
                    "tracks": tracks
                }, f, indent=2)
            
            # Create Spotify playlist
            creator = SpotifyPlaylistCreator()
            playlist_url, added, not_found = creator.create_playlist(
                tracks, 
                mix_name,
                f"Identified from: {url}"
            )
            
            # Send success message
            track_list_preview = "\n".join(
                f"  • {t['artist']} - {t['title']}"
                for t in tracks[:10]
            )
            if len(tracks) > 10:
                track_list_preview += f"\n  ... and {len(tracks) - 10} more"
            
            await update.message.reply_text(
                f"✅ Playlist created!\n\n"
                f"🎧 {playlist_url}\n\n"
                f"📊 Stats:\n"
                f"  • Tracks found: {len(tracks)}\n"
                f"  • Added to Spotify: {added}\n"
                f"  • Not on Spotify: {not_found}\n\n"
                f"🎵 Tracks:\n{track_list_preview}"
            )
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}\n\n"
            f"Please try again or contact the bot admin."
        )
    
    finally:
        active_jobs[user_id] = False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Welcome to SoundCloud to Spotify Bot!\n\n"
        "Send me a SoundCloud mix URL and I'll:\n"
        "1. 📥 Download the audio\n"
        "2. 🔍 Identify all the tracks using Shazam\n"
        "3. 🎧 Create a Spotify playlist for you\n\n"
        "Just paste a link like:\n"
        "https://soundcloud.com/artist/mix-name\n\n"
        "⏱️ Note: Long mixes (1-2 hours) may take 5-10 minutes to process."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "🔧 How to use this bot:\n\n"
        "1. Find a mix on SoundCloud\n"
        "2. Copy the URL\n"
        "3. Paste it here\n"
        "4. Wait for the magic! ✨\n\n"
        "Commands:\n"
        "/start - Welcome message\n"
        "/help - This help message\n"
        "/status - Check if a job is running\n\n"
        "Tips:\n"
        "• Works best with DJ mixes that play full tracks\n"
        "• Heavily mixed/layered sections may not be identified\n"
        "• Private SoundCloud links work too!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = update.effective_user.id
    if active_jobs.get(user_id):
        await update.message.reply_text("⏳ You have a mix being processed. Please wait!")
    else:
        await update.message.reply_text("✅ No active jobs. Send me a SoundCloud URL!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    text = update.message.text
    
    # Check for SoundCloud URL
    match = SOUNDCLOUD_REGEX.search(text)
    if match:
        url = match.group(0)
        await process_soundcloud_url(update, context, url)
    else:
        await update.message.reply_text(
            "🤔 I don't see a SoundCloud URL in your message.\n\n"
            "Send me a link like:\n"
            "https://soundcloud.com/artist/mix-name"
        )


def main():
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set!")
        print("   Get a token from @BotFather on Telegram")
        print("   Add it to your .env file")
        return
    
    if not os.getenv("SPOTIPY_CLIENT_ID") or not os.getenv("SPOTIPY_CLIENT_SECRET"):
        print("❌ Error: Spotify credentials not set!")
        print("   Add SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET to .env")
        return
    
    print("🤖 Starting SoundCloud to Spotify Bot...")
    print("   Press Ctrl+C to stop")
    
    # Create application
    app = Application.builder().token(token).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

