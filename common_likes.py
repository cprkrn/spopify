#!/usr/bin/env python3
"""
SoundCloud Common Likes Finder

Finds tracks that multiple SoundCloud artists have liked,
then creates a Spotify playlist with those tracks.
"""

import argparse
import json
import re
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from soundcloud import SoundCloud
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


@dataclass
class Track:
    """Represents a SoundCloud track."""
    id: int
    title: str
    artist: str
    url: str
    
    def __hash__(self):
        return self.id
    
    def __eq__(self, other):
        return self.id == other.id


def get_artist_likes(sc: SoundCloud, artist_url: str, limit: int = 200) -> tuple[str, list[Track]]:
    """Get an artist's name and their liked tracks."""
    try:
        # Resolve the URL to get user info
        user = sc.resolve(artist_url)
        if not user:
            return None, []
        
        username = user.username
        user_id = user.id
        
        # Fetch likes
        tracks = []
        for like in sc.get_user_likes(user_id):
            if len(tracks) >= limit:
                break
            
            # Likes can be tracks or playlists
            if hasattr(like, 'track') and like.track:
                track = like.track
                tracks.append(Track(
                    id=track.id,
                    title=track.title or "Unknown",
                    artist=track.user.username if track.user else "Unknown",
                    url=track.permalink_url or ""
                ))
        
        return username, tracks
    
    except Exception as e:
        print(f"   ⚠️ Error fetching {artist_url}: {e}")
        return None, []


def find_common_likes(artist_likes: dict[str, list[Track]], min_artists: int = 2) -> list[tuple[Track, list[str]]]:
    """
    Find tracks liked by multiple artists.
    
    Returns list of (track, [artists who liked it]) sorted by number of artists.
    """
    # Count how many artists liked each track
    track_to_artists: dict[int, tuple[Track, list[str]]] = {}
    
    for artist_name, tracks in artist_likes.items():
        for track in tracks:
            if track.id not in track_to_artists:
                track_to_artists[track.id] = (track, [])
            track_to_artists[track.id][1].append(artist_name)
    
    # Filter to tracks liked by at least min_artists
    common = [
        (track, artists) 
        for track, artists in track_to_artists.values() 
        if len(artists) >= min_artists
    ]
    
    # Sort by number of artists (descending), then by track title
    common.sort(key=lambda x: (-len(x[1]), x[0].title.lower()))
    
    return common


class SpotifyPlaylistCreator:
    """Handles Spotify playlist creation."""
    
    def __init__(self):
        self.spotify = spotipy.Spotify(auth_manager=SpotifyOAuth(
            scope="playlist-modify-public playlist-modify-private",
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")
        ))
    
    def search_track(self, title: str, artist: str) -> tuple[str, str] | None:
        """
        Search for a track on Spotify.
        Returns (uri, spotify_name) or None.
        """
        # Clean up title - remove common suffixes
        clean_title = re.sub(r'\s*[\[\(].*?(?:remix|mix|edit|version|original).*?[\]\)]', '', title, flags=re.IGNORECASE)
        clean_title = clean_title.strip()
        
        # Try exact search first
        query = f"track:{clean_title} artist:{artist}"
        try:
            results = self.spotify.search(q=query, type="track", limit=1)
            if results["tracks"]["items"]:
                track = results["tracks"]["items"][0]
                name = f"{track['artists'][0]['name']} - {track['name']}"
                return track["uri"], name
            
            # Fallback: relaxed search
            query = f"{artist} {clean_title}"
            results = self.spotify.search(q=query, type="track", limit=3)
            if results["tracks"]["items"]:
                # Try to find best match
                for track in results["tracks"]["items"]:
                    track_name = track["name"].lower()
                    if clean_title.lower() in track_name or track_name in clean_title.lower():
                        name = f"{track['artists'][0]['name']} - {track['name']}"
                        return track["uri"], name
                
                # Just use first result
                track = results["tracks"]["items"][0]
                name = f"{track['artists'][0]['name']} - {track['name']}"
                return track["uri"], name
        
        except Exception as e:
            print(f"   ⚠️ Spotify error: {e}")
        
        return None
    
    def create_playlist(self, name: str, tracks: list[tuple[str, str]], description: str = "") -> str:
        """
        Create a playlist with the given tracks.
        tracks: list of (uri, display_name)
        Returns playlist URL.
        """
        user = self.spotify.current_user()
        user_id = user["id"]
        
        playlist = self.spotify.user_playlist_create(
            user=user_id,
            name=f"[Common Likes] {name}",
            public=True,
            description=description
        )
        playlist_id = playlist["id"]
        playlist_url = playlist["external_urls"]["spotify"]
        
        # Add tracks
        uris = [uri for uri, _ in tracks]
        if uris:
            for i in range(0, len(uris), 100):
                batch = uris[i:i + 100]
                self.spotify.playlist_add_items(playlist_id, batch)
        
        return playlist_url


def main():
    parser = argparse.ArgumentParser(
        description="Find tracks liked by multiple SoundCloud artists and create a Spotify playlist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://soundcloud.com/janefitz https://soundcloud.com/bobby https://soundcloud.com/chez-demilo
  %(prog)s janefitz bobby chez-demilo --min-artists 2 --name "Common Vibes"
  %(prog)s artist1 artist2 artist3 --limit 500 --save-json results.json
        """
    )
    
    parser.add_argument(
        "artists",
        nargs="+",
        help="SoundCloud artist URLs or usernames"
    )
    parser.add_argument(
        "--min-artists", "-m",
        type=int,
        default=2,
        help="Minimum number of artists that must like a track (default: 2)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=200,
        help="Maximum likes to fetch per artist (default: 200)"
    )
    parser.add_argument(
        "--name", "-n",
        help="Playlist name (default: auto-generated from artist names)"
    )
    parser.add_argument(
        "--save-json", "-j",
        help="Save results to JSON file"
    )
    parser.add_argument(
        "--no-spotify",
        action="store_true",
        help="Don't create Spotify playlist, just show results"
    )
    
    args = parser.parse_args()
    
    # Normalize artist URLs
    artist_urls = []
    for artist in args.artists:
        if not artist.startswith("http"):
            artist = f"https://soundcloud.com/{artist}"
        artist_urls.append(artist)
    
    print(f"🎵 Analyzing {len(artist_urls)} artists...\n")
    
    # Initialize SoundCloud client
    sc = SoundCloud()
    
    # Fetch likes for each artist
    artist_likes: dict[str, list[Track]] = {}
    
    for url in artist_urls:
        print(f"📥 Fetching likes from: {url}")
        name, tracks = get_artist_likes(sc, url, limit=args.limit)
        
        if name and tracks:
            artist_likes[name] = tracks
            print(f"   ✅ {name}: {len(tracks)} likes")
        else:
            print(f"   ❌ Could not fetch likes")
    
    if len(artist_likes) < 2:
        print("\n❌ Need at least 2 artists to find common likes!")
        return
    
    # Find common likes
    print(f"\n🔍 Finding tracks liked by {args.min_artists}+ artists...")
    common = find_common_likes(artist_likes, min_artists=args.min_artists)
    
    if not common:
        print(f"😕 No tracks found that {args.min_artists}+ artists have in common.")
        print("   Try lowering --min-artists or fetching more --limit likes.")
        return
    
    print(f"\n🎉 Found {len(common)} tracks in common!\n")
    
    # Display results
    print("=" * 60)
    for i, (track, artists) in enumerate(common[:30], 1):  # Show top 30
        artist_str = ", ".join(artists)
        print(f"{i:2}. {track.artist} - {track.title}")
        print(f"    Liked by: {artist_str}")
        print(f"    {track.url}")
        print()
    
    if len(common) > 30:
        print(f"   ... and {len(common) - 30} more tracks\n")
    
    print("=" * 60)
    
    # Save to JSON if requested
    if args.save_json:
        data = {
            "artists": list(artist_likes.keys()),
            "min_artists": args.min_artists,
            "common_tracks": [
                {
                    "title": track.title,
                    "artist": track.artist,
                    "url": track.url,
                    "liked_by": artists
                }
                for track, artists in common
            ]
        }
        with open(args.save_json, "w") as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved results to: {args.save_json}\n")
    
    # Create Spotify playlist
    if not args.no_spotify:
        if not os.getenv("SPOTIPY_CLIENT_ID"):
            print("⚠️ No Spotify credentials found. Skipping playlist creation.")
            print("   Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in .env")
            return
        
        print("🎧 Creating Spotify playlist...")
        
        creator = SpotifyPlaylistCreator()
        spotify_tracks = []
        not_found = []
        
        for track, artists in common:
            result = creator.search_track(track.title, track.artist)
            if result:
                uri, name = result
                spotify_tracks.append((uri, name))
                print(f"   ✅ Found: {name}")
            else:
                not_found.append(track)
                print(f"   ❌ Not found: {track.artist} - {track.title}")
        
        if spotify_tracks:
            playlist_name = args.name or " × ".join(artist_likes.keys())
            description = f"Tracks liked by: {', '.join(artist_likes.keys())}"
            
            playlist_url = creator.create_playlist(playlist_name, spotify_tracks, description)
            
            print(f"\n{'=' * 60}")
            print(f"✅ Playlist created!")
            print(f"   🎧 {playlist_url}")
            print(f"   Added: {len(spotify_tracks)} tracks")
            if not_found:
                print(f"   Not on Spotify: {len(not_found)} tracks")
        else:
            print("\n❌ No tracks found on Spotify!")


if __name__ == "__main__":
    main()
