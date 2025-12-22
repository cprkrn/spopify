#!/usr/bin/env python3
"""
SoundCloud Mix to Spotify Playlist Converter

This script:
1. Downloads audio from a SoundCloud URL
2. Segments it and identifies songs using Shazam
3. Creates a Spotify playlist with the identified tracks
"""

import asyncio
import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment
from shazamio import Shazam
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


@dataclass
class IdentifiedTrack:
    """Represents a track identified by Shazam."""
    title: str
    artist: str
    timestamp_seconds: int
    shazam_id: Optional[str] = None
    spotify_uri: Optional[str] = None


class SoundCloudToSpotify:
    def __init__(
        self,
        segment_duration_sec: int = 20,
        segment_step_sec: int = 30,
        verbose: bool = True
    ):
        """
        Initialize the converter.
        
        Args:
            segment_duration_sec: Length of each audio segment to analyze (seconds)
            segment_step_sec: How far to advance between segments (seconds)
            verbose: Print progress information
        """
        self.segment_duration = segment_duration_sec * 1000  # Convert to ms
        self.segment_step = segment_step_sec * 1000  # Convert to ms
        self.verbose = verbose
        
        # Initialize Spotify client
        self.spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="playlist-modify-public playlist-modify-private",
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")
        ))
    
    def log(self, message: str):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message, flush=True)
    
    def download_audio(self, url: str, output_dir: str) -> str:
        """
        Download audio from SoundCloud URL.
        
        Returns path to the downloaded audio file.
        """
        self.log(f"📥 Downloading audio from: {url}")
        
        output_template = os.path.join(output_dir, "audio.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", output_template,
            url
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to download audio: {e.stderr}")
        
        # Find the downloaded file
        for ext in ["mp3", "m4a", "wav", "ogg"]:
            path = os.path.join(output_dir, f"audio.{ext}")
            if os.path.exists(path):
                self.log(f"✅ Downloaded: {path}")
                return path
        
        raise RuntimeError("Downloaded file not found")
    
    async def identify_segment(self, audio_segment: AudioSegment, timestamp_sec: int, retries: int = 2) -> Optional[IdentifiedTrack]:
        """
        Identify a single audio segment using Shazam.
        """
        # Export segment to temporary file (use raw format for speed)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            audio_segment.export(tmp.name, format="mp3", bitrate="128k")
            tmp_path = tmp.name
        
        try:
            for attempt in range(retries + 1):
                try:
                    # Create fresh Shazam instance for each request
                    shazam = Shazam()
                    result = await asyncio.wait_for(
                        shazam.recognize(tmp_path),
                        timeout=15.0
                    )
                    
                    if result and "track" in result:
                        track = result["track"]
                        return IdentifiedTrack(
                            title=track.get("title", "Unknown"),
                            artist=track.get("subtitle", "Unknown"),
                            timestamp_seconds=timestamp_sec,
                            shazam_id=track.get("key")
                        )
                    return None  # No match but successful request
                    
                except asyncio.TimeoutError:
                    if attempt < retries:
                        self.log(f"   ⏳ Retry {attempt + 1}/{retries} at {timestamp_sec}s...")
                        await asyncio.sleep(3)  # Wait before retry
                    else:
                        self.log(f"   ⚠️  Timeout at {timestamp_sec}s after {retries + 1} attempts")
                except Exception as e:
                    if attempt < retries:
                        await asyncio.sleep(2)
                    else:
                        self.log(f"   ⚠️  Shazam error at {timestamp_sec}s: {e}")
        finally:
            os.unlink(tmp_path)
        
        return None
    
    async def identify_tracks(self, audio_path: str) -> list[IdentifiedTrack]:
        """
        Identify all tracks in an audio file by segmenting and analyzing.
        """
        self.log(f"🎵 Loading audio file: {audio_path}")
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)
        duration_sec = duration_ms // 1000
        
        self.log(f"⏱️  Duration: {duration_sec // 60}m {duration_sec % 60}s")
        self.log(f"🔍 Analyzing segments (every {self.segment_step // 1000}s)...")
        
        identified_tracks: list[IdentifiedTrack] = []
        seen_tracks: set[tuple[str, str]] = set()  # (title, artist) pairs
        
        position = 0
        request_count = 0
        while position + self.segment_duration <= duration_ms:
            timestamp_sec = position // 1000
            progress_pct = (position / duration_ms) * 100
            
            self.log(f"   [{progress_pct:5.1f}%] Analyzing at {timestamp_sec // 60}:{timestamp_sec % 60:02d}...")
            
            # Add delay every few requests to avoid rate limiting
            request_count += 1
            if request_count > 1:
                await asyncio.sleep(2)  # 2 second delay between requests
            
            segment = audio[position:position + self.segment_duration]
            track = await self.identify_segment(segment, timestamp_sec)
            
            if track:
                track_key = (track.title.lower(), track.artist.lower())
                if track_key not in seen_tracks:
                    seen_tracks.add(track_key)
                    identified_tracks.append(track)
                    self.log(f"   ✅ Found: {track.artist} - {track.title}")
                else:
                    self.log(f"   ⏭️  Already found: {track.artist} - {track.title}")
            else:
                self.log(f"   ❌ No match")
            
            position += self.segment_step
        
        self.log(f"\n🎉 Identified {len(identified_tracks)} unique tracks!")
        return identified_tracks
    
    def search_spotify_track(self, track: IdentifiedTrack) -> Optional[str]:
        """
        Search for a track on Spotify and return its URI.
        """
        query = f"track:{track.title} artist:{track.artist}"
        
        try:
            results = self.spotify.search(q=query, type="track", limit=1)
            
            if results["tracks"]["items"]:
                spotify_track = results["tracks"]["items"][0]
                return spotify_track["uri"]
            
            # Try a more relaxed search
            query = f"{track.artist} {track.title}"
            results = self.spotify.search(q=query, type="track", limit=1)
            
            if results["tracks"]["items"]:
                spotify_track = results["tracks"]["items"][0]
                return spotify_track["uri"]
        
        except Exception as e:
            self.log(f"   ⚠️  Spotify search error: {e}")
        
        return None
    
    def create_spotify_playlist(
        self,
        tracks: list[IdentifiedTrack],
        playlist_name: str,
        playlist_description: str = ""
    ) -> str:
        """
        Create a Spotify playlist with the identified tracks.
        
        Returns the playlist URL.
        """
        self.log(f"\n🎧 Creating Spotify playlist: {playlist_name}")
        
        # Get current user
        user = self.spotify.current_user()
        user_id = user["id"]
        
        # Create playlist
        playlist = self.spotify.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=True,
            description=playlist_description
        )
        playlist_id = playlist["id"]
        playlist_url = playlist["external_urls"]["spotify"]
        
        self.log(f"📝 Playlist created: {playlist_url}")
        
        # Find tracks on Spotify
        self.log("🔍 Searching for tracks on Spotify...")
        spotify_uris: list[str] = []
        not_found: list[IdentifiedTrack] = []
        
        for track in tracks:
            uri = self.search_spotify_track(track)
            if uri:
                spotify_uris.append(uri)
                track.spotify_uri = uri
                self.log(f"   ✅ Found: {track.artist} - {track.title}")
            else:
                not_found.append(track)
                self.log(f"   ❌ Not found: {track.artist} - {track.title}")
        
        # Add tracks to playlist (in batches of 100)
        if spotify_uris:
            self.log(f"➕ Adding {len(spotify_uris)} tracks to playlist...")
            for i in range(0, len(spotify_uris), 100):
                batch = spotify_uris[i:i + 100]
                self.spotify.playlist_add_items(playlist_id, batch)
        
        # Summary
        self.log(f"\n{'='*50}")
        self.log(f"✅ Playlist created successfully!")
        self.log(f"   Added: {len(spotify_uris)} tracks")
        self.log(f"   Not found: {len(not_found)} tracks")
        self.log(f"   URL: {playlist_url}")
        
        if not_found:
            self.log(f"\n⚠️  Tracks not found on Spotify:")
            for track in not_found:
                self.log(f"   - {track.artist} - {track.title}")
        
        return playlist_url
    
    async def convert(
        self,
        soundcloud_url: str,
        playlist_name: Optional[str] = None,
        playlist_description: str = ""
    ) -> str:
        """
        Main conversion method. Downloads, identifies, and creates playlist.
        
        Returns the Spotify playlist URL.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Download audio
            audio_path = self.download_audio(soundcloud_url, tmp_dir)
            
            # Identify tracks
            tracks = await self.identify_tracks(audio_path)
            
            if not tracks:
                raise RuntimeError("No tracks were identified in the audio")
            
            # Create playlist
            if not playlist_name:
                playlist_name = f"SoundCloud Mix ({len(tracks)} tracks)"
            
            # Add prefix for easy grouping
            playlist_name = f"[SCF] {playlist_name}"
            
            return self.create_spotify_playlist(tracks, playlist_name, playlist_description)


async def main():
    parser = argparse.ArgumentParser(
        description="Convert a SoundCloud mix to a Spotify playlist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://soundcloud.com/artist/mix-name
  %(prog)s https://soundcloud.com/artist/mix-name --name "My Playlist"
  %(prog)s https://soundcloud.com/artist/mix-name --segment-duration 15 --segment-step 20

Environment variables required:
  SPOTIPY_CLIENT_ID     - Your Spotify app client ID
  SPOTIPY_CLIENT_SECRET - Your Spotify app client secret
  SPOTIPY_REDIRECT_URI  - Redirect URI (default: http://localhost:8888/callback)
        """
    )
    
    parser.add_argument(
        "url",
        help="SoundCloud URL of the mix"
    )
    parser.add_argument(
        "--name", "-n",
        dest="playlist_name",
        help="Name for the Spotify playlist"
    )
    parser.add_argument(
        "--description", "-d",
        dest="playlist_description",
        default="",
        help="Description for the Spotify playlist"
    )
    parser.add_argument(
        "--segment-duration",
        type=int,
        default=20,
        help="Duration of each audio segment to analyze in seconds (default: 20)"
    )
    parser.add_argument(
        "--segment-step",
        type=int,
        default=45,
        help="Time between segment starts in seconds (default: 45)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    
    args = parser.parse_args()
    
    # Check for required environment variables
    if not os.getenv("SPOTIPY_CLIENT_ID") or not os.getenv("SPOTIPY_CLIENT_SECRET"):
        print("❌ Error: Missing Spotify API credentials!")
        print("   Please set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables.")
        print("   You can get these from https://developer.spotify.com/dashboard")
        sys.exit(1)
    
    converter = SoundCloudToSpotify(
        segment_duration_sec=args.segment_duration,
        segment_step_sec=args.segment_step,
        verbose=not args.quiet
    )
    
    try:
        playlist_url = await converter.convert(
            soundcloud_url=args.url,
            playlist_name=args.playlist_name,
            playlist_description=args.playlist_description
        )
        print(f"\n🎉 Done! Playlist: {playlist_url}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

