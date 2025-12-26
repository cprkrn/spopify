#!/usr/bin/env python3
"""
Create a SoundCloud playlist from a list of track URLs.

Opens a browser for you to log in, then creates the playlist automatically.
"""

import asyncio
import argparse
import json
from playwright.async_api import async_playwright


async def create_playlist(track_urls: list[str], playlist_name: str):
    """Create a SoundCloud playlist with the given tracks."""
    
    async with async_playwright() as p:
        # Launch browser (not headless so user can log in)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Go to SoundCloud
        print("🌐 Opening SoundCloud...")
        await page.goto("https://soundcloud.com")
        await page.wait_for_load_state("networkidle")
        
        # Check if already logged in
        try:
            await page.wait_for_selector('[aria-label="Your profile"]', timeout=3000)
            print("✅ Already logged in!")
        except:
            # Need to log in
            print("\n👤 Please log in to SoundCloud in the browser window...")
            print("   (waiting for you to complete login)\n")
            
            # Click sign in button
            try:
                sign_in = await page.wait_for_selector('button:has-text("Sign in")', timeout=5000)
                await sign_in.click()
            except:
                pass
            
            # Wait for user to log in (wait for profile button to appear)
            try:
                await page.wait_for_selector('[aria-label="Your profile"]', timeout=120000)
                print("✅ Login successful!")
            except:
                print("❌ Login timed out. Please try again.")
                await browser.close()
                return None
        
        await asyncio.sleep(1)
        
        # Go to library/playlists to create new playlist
        print("\n📝 Creating new playlist...")
        await page.goto("https://soundcloud.com/you/library/playlists")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Click "Create playlist" or similar button
        try:
            # Try different selectors for create playlist button
            create_btn = await page.query_selector('button:has-text("Create playlist")')
            if not create_btn:
                create_btn = await page.query_selector('a:has-text("Create playlist")')
            if not create_btn:
                create_btn = await page.query_selector('[title="Create playlist"]')
            
            if create_btn:
                await create_btn.click()
                await asyncio.sleep(2)
        except Exception as e:
            print(f"   Could not find create button: {e}")
        
        # Alternative: Go to first track and use "Add to playlist" -> "Create new playlist"
        print("📥 Adding tracks to playlist...")
        
        first_track = True
        for i, url in enumerate(track_urls, 1):
            print(f"   [{i}/{len(track_urls)}] Adding: {url.split('/')[-1][:40]}...")
            
            try:
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1.5)
                
                # Find the "More" or "..." button on the track
                more_btn = await page.query_selector('[aria-label="More"]')
                if not more_btn:
                    more_btn = await page.query_selector('button[aria-haspopup="true"]')
                if not more_btn:
                    more_btn = await page.query_selector('.sc-button-more')
                
                if more_btn:
                    await more_btn.click()
                    await asyncio.sleep(0.5)
                    
                    # Click "Add to playlist"
                    add_to_playlist = await page.query_selector('button:has-text("Add to playlist")')
                    if not add_to_playlist:
                        add_to_playlist = await page.query_selector('[title*="Add to playlist"]')
                    
                    if add_to_playlist:
                        await add_to_playlist.click()
                        await asyncio.sleep(1)
                        
                        if first_track:
                            # Create new playlist
                            create_new = await page.query_selector('button:has-text("Create a playlist")')
                            if not create_new:
                                create_new = await page.query_selector('input[placeholder*="Playlist"]')
                            
                            if create_new:
                                await create_new.click()
                                await asyncio.sleep(0.5)
                            
                            # Enter playlist name
                            name_input = await page.query_selector('input[type="text"]')
                            if name_input:
                                await name_input.fill(playlist_name)
                                await asyncio.sleep(0.5)
                            
                            # Click save/create
                            save_btn = await page.query_selector('button:has-text("Save")')
                            if not save_btn:
                                save_btn = await page.query_selector('button:has-text("Create")')
                            if save_btn:
                                await save_btn.click()
                                await asyncio.sleep(1)
                            
                            first_track = False
                        else:
                            # Add to existing playlist
                            playlist_option = await page.query_selector(f'button:has-text("{playlist_name}")')
                            if not playlist_option:
                                # Find playlist in list
                                playlist_items = await page.query_selector_all('.addToPlaylistList__item')
                                for item in playlist_items:
                                    text = await item.inner_text()
                                    if playlist_name.lower() in text.lower():
                                        await item.click()
                                        break
                            else:
                                await playlist_option.click()
                            
                            await asyncio.sleep(0.5)
                        
                        # Close modal if open
                        close_btn = await page.query_selector('[aria-label="Close"]')
                        if close_btn:
                            await close_btn.click()
                
            except Exception as e:
                print(f"      ⚠️ Error: {e}")
                continue
        
        print("\n✅ Done! Check your SoundCloud playlists.")
        print("   Press Enter to close the browser...")
        input()
        
        await browser.close()
        return True


def main():
    parser = argparse.ArgumentParser(description="Create a SoundCloud playlist from track URLs")
    parser.add_argument("--name", "-n", required=True, help="Playlist name")
    parser.add_argument("--urls", "-u", nargs="+", help="Track URLs")
    parser.add_argument("--file", "-f", help="JSON file with track URLs (from common_likes.py --save-json)")
    
    args = parser.parse_args()
    
    track_urls = []
    
    if args.file:
        with open(args.file) as f:
            data = json.load(f)
            track_urls = [t["url"] for t in data.get("common_tracks", [])]
    elif args.urls:
        track_urls = args.urls
    else:
        print("❌ Provide either --urls or --file")
        return
    
    if not track_urls:
        print("❌ No track URLs provided")
        return
    
    print(f"🎵 Creating playlist '{args.name}' with {len(track_urls)} tracks\n")
    
    asyncio.run(create_playlist(track_urls, args.name))


if __name__ == "__main__":
    main()

