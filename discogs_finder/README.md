# Discogs to Spotify Finder

Scrapes a Discogs seller's inventory and creates a Spotify playlist from matching releases.

## Usage

```bash
# Basic usage - scrape first 50 items
python3 discogs_finder/discogs_to_spotify.py "https://www.discogs.com/seller/SELLER_NAME/profile"

# With custom playlist name and limit
python3 discogs_finder/discogs_to_spotify.py "https://www.discogs.com/seller/houseofdog/profile" \
  --name "House of Dog Records" \
  --limit 100

# Save results to JSON without creating playlist
python3 discogs_finder/discogs_to_spotify.py "https://www.discogs.com/seller/houseofdog/profile" \
  --save-json results.json \
  --no-playlist
```

## Options

| Option | Description |
|--------|-------------|
| `--name`, `-n` | Spotify playlist name (default: "Discogs Finds") |
| `--limit`, `-l` | Max items to scrape (default: 50) |
| `--save-json`, `-s` | Save results to JSON file |
| `--no-playlist` | Skip creating Spotify playlist |

## How it works

1. Uses Playwright to scrape the seller's inventory page
2. Extracts artist, title, format, and price for each listing
3. Searches Spotify for matching albums/tracks
4. Creates a playlist with all tracks from matched albums

