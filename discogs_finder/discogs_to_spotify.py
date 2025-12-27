#!/usr/bin/env python3
"""
Discogs to Spotify Playlist Creator

Scrapes a Discogs seller's inventory and finds matching tracks on Spotify,
then creates a playlist from the matches.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

# Add parent directory to path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def clean_title(title: str) -> str:
    """Clean up a release title for better Spotify matching."""
    # Remove common suffixes/prefixes that hurt matching
    title = re.sub(r'\s*\([^)]*remix[^)]*\)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\([^)]*remaster[^)]*\)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\([^)]*edition[^)]*\)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\([^)]*version[^)]*\)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*EP$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*LP$', '', title, flags=re.IGNORECASE)
    # Remove catalog numbers like [CAT123]
    title = re.sub(r'\s*\[[^\]]+\]', '', title)
    return title.strip()


async def scrape_discogs_inventory(seller_url: str, limit: int = 50) -> list[dict]:
    """
    Scrape inventory from a Discogs seller page using Playwright.
    
    Args:
        seller_url: URL to the seller's inventory page
        limit: Maximum number of items to scrape
        
    Returns:
        List of dicts with artist, title, format, price, and url
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright not installed. Run: pip install playwright && playwright install")
        sys.exit(1)
    
    # Convert profile URL to inventory URL if needed
    if '/profile' in seller_url:
        seller_url = seller_url.replace('/profile', '')
    if not '/inventory' in seller_url:
        # Extract seller name and build inventory URL
        match = re.search(r'/seller/([^/?]+)', seller_url)
        if match:
            seller_name = match.group(1)
            seller_url = f"https://www.discogs.com/seller/{seller_name}/profile?sort=listed%2Cdesc&limit={min(limit, 250)}"
    
    print(f"📦 Scraping inventory from: {seller_url}")
    
    items = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        try:
            await page.goto(seller_url, wait_until='networkidle', timeout=30000)
            
            # Wait for inventory items to load
            await page.wait_for_selector('.shortcut_navigable', timeout=10000)
            
            # Get all inventory rows
            rows = await page.query_selector_all('.shortcut_navigable')
            
            for row in rows[:limit]:
                try:
                    # Get the release title link
                    title_elem = await row.query_selector('.item_description_title')
                    if not title_elem:
                        continue
                    
                    title_text = await title_elem.inner_text()
                    href = await title_elem.get_attribute('href')
                    
                    # Parse "Artist - Title" format
                    if ' - ' in title_text:
                        artist, title = title_text.split(' - ', 1)
                    else:
                        artist = "Unknown"
                        title = title_text
                    
                    # Get price
                    price_elem = await row.query_selector('.price')
                    price = await price_elem.inner_text() if price_elem else "N/A"
                    
                    # Get format (Vinyl, CD, etc)
                    format_elem = await row.query_selector('.item_format')
                    format_type = await format_elem.inner_text() if format_elem else "Unknown"
                    
                    items.append({
                        'artist': artist.strip(),
                        'title': title.strip(),
                        'format': format_type.strip(),
                        'price': price.strip(),
                        'url': f"https://discogs.com{href}" if href else None
                    })
                    
                except Exception as e:
                    continue
            
        except Exception as e:
            print(f"⚠️  Error scraping: {e}")
            print("💡 Tip: The page might have Cloudflare protection. Try running with --headless=false")
        
        await browser.close()
    
    print(f"📀 Found {len(items)} items in inventory")
    return items


def search_spotify(sp: spotipy.Spotify, artist: str, title: str) -> dict | None:
    """
    Search Spotify for a release.
    
    Returns the first matching album or track, or None if not found.
    """
    # Clean up the title
    clean = clean_title(title)
    
    # Try album search first
    query = f"artist:{artist} album:{clean}"
    try:
        results = sp.search(q=query, type='album', limit=1)
        if results['albums']['items']:
            album = results['albums']['items'][0]
            return {
                'type': 'album',
                'name': album['name'],
                'artist': album['artists'][0]['name'],
                'uri': album['uri'],
                'url': album['external_urls']['spotify'],
                'id': album['id']
            }
    except Exception:
        pass
    
    # Try track search as fallback
    query = f"artist:{artist} track:{clean}"
    try:
        results = sp.search(q=query, type='track', limit=1)
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            return {
                'type': 'track',
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'uri': track['uri'],
                'url': track['external_urls']['spotify'],
                'id': track['id']
            }
    except Exception:
        pass
    
    # Try a broader search without artist constraint
    try:
        results = sp.search(q=f"{artist} {clean}", type='album', limit=1)
        if results['albums']['items']:
            album = results['albums']['items'][0]
            return {
                'type': 'album',
                'name': album['name'],
                'artist': album['artists'][0]['name'],
                'uri': album['uri'],
                'url': album['external_urls']['spotify'],
                'id': album['id']
            }
    except Exception:
        pass
    
    return None


def create_spotify_playlist(sp: spotipy.Spotify, name: str, tracks: list[dict]) -> str:
    """
    Create a Spotify playlist from found tracks/albums.
    
    For albums, adds all tracks from the album.
    For tracks, adds the track directly.
    
    Returns the playlist URL.
    """
    user_id = sp.current_user()['id']
    
    playlist = sp.user_playlist_create(
        user_id,
        name,
        public=True,
        description="Created from Discogs seller inventory"
    )
    
    track_uris = []
    
    for item in tracks:
        if item['type'] == 'album':
            # Get all tracks from the album
            try:
                album_tracks = sp.album_tracks(item['id'])
                for track in album_tracks['items']:
                    track_uris.append(track['uri'])
            except Exception:
                pass
        else:
            track_uris.append(item['uri'])
    
    # Add tracks in batches of 100 (Spotify limit)
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        sp.playlist_add_items(playlist['id'], batch)
    
    return playlist['external_urls']['spotify']


async def main():
    parser = argparse.ArgumentParser(
        description='Create Spotify playlist from Discogs seller inventory',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.discogs.com/seller/houseofdog/profile"
  %(prog)s "https://www.discogs.com/seller/houseofdog/profile" --name "House of Dog Records"
  %(prog)s "https://www.discogs.com/seller/houseofdog/profile" --limit 100 --save-json results.json
        """
    )
    
    parser.add_argument('seller_url', help='Discogs seller URL')
    parser.add_argument('--name', '-n', default='Discogs Finds',
                        help='Name for the Spotify playlist')
    parser.add_argument('--limit', '-l', type=int, default=50,
                        help='Maximum items to scrape (default: 50)')
    parser.add_argument('--save-json', '-s', type=str,
                        help='Save results to JSON file')
    parser.add_argument('--no-playlist', action='store_true',
                        help='Skip creating Spotify playlist')
    
    args = parser.parse_args()
    
    print("🎵 Discogs to Spotify Finder")
    print("=" * 40)
    
    # Scrape inventory
    items = await scrape_discogs_inventory(args.seller_url, args.limit)
    
    if not items:
        print("❌ No items found in inventory")
        return
    
    # Initialize Spotify
    print("\n🔍 Searching Spotify for matches...")
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="playlist-modify-public playlist-modify-private"
    ))
    
    found = []
    not_found = []
    
    for i, item in enumerate(items, 1):
        print(f"  [{i}/{len(items)}] {item['artist']} - {item['title']}... ", end='', flush=True)
        
        result = search_spotify(sp, item['artist'], item['title'])
        
        if result:
            result['discogs'] = item
            found.append(result)
            print(f"✅ {result['type']}: {result['name']}")
        else:
            not_found.append(item)
            print("❌ Not found")
    
    # Summary
    print(f"\n📊 Results: {len(found)}/{len(items)} found on Spotify")
    
    if args.save_json:
        output = {
            'found': found,
            'not_found': not_found,
            'source_url': args.seller_url
        }
        with open(args.save_json, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"💾 Saved results to {args.save_json}")
    
    # Create playlist
    if found and not args.no_playlist:
        print(f"\n🎧 Creating Spotify playlist: {args.name}")
        playlist_url = create_spotify_playlist(sp, args.name, found)
        print(f"✅ Playlist created: {playlist_url}")
    elif not found:
        print("❌ No matches found to create playlist")
    
    # Show not found items
    if not_found:
        print(f"\n⚠️  {len(not_found)} items not found on Spotify:")
        for item in not_found[:10]:
            print(f"   • {item['artist']} - {item['title']}")
        if len(not_found) > 10:
            print(f"   ... and {len(not_found) - 10} more")


if __name__ == '__main__':
    asyncio.run(main())

