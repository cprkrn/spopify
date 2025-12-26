# SoundCloud to Spotify Playlist Converter

Automatically identify songs in a SoundCloud mix using Shazam and create a Spotify playlist.

## How It Works

1. **Download** - Fetches audio from SoundCloud using `yt-dlp`
2. **Identify** - Splits the mix into segments and identifies each song using Shazam
3. **Create Playlist** - Searches for identified songs on Spotify and creates a playlist

## Installation

### Prerequisites

- Python 3.10+ (Python 3.13 supported)
- FFmpeg (required for audio processing)

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### Install Dependencies

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/scf.git
cd scf

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt

# Python 3.13+ only: install audioop compatibility package
pip install audioop-lts
```

## Setup

### 1. Create a Spotify App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **"Create App"**
3. Fill in the details:
   - **App name**: `SoundCloud to Spotify` (or whatever you want)
   - **App description**: Anything
   - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ Must match exactly!
4. Click **Save**
5. Go to **Settings** and note your **Client ID** and **Client Secret**

### 2. Configure Environment Variables

Create a `.env` file with your credentials:

```bash
cp env.example .env
```

Edit `.env`:
```
SPOTIPY_CLIENT_ID=your_client_id_here
SPOTIPY_CLIENT_SECRET=your_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Usage

### Basic Usage

```bash
python3 soundcloud_to_spotify.py "https://soundcloud.com/artist/mix-name"
```

### With Custom Playlist Name

```bash
python3 soundcloud_to_spotify.py "https://soundcloud.com/artist/mix-name" \
    --name "My Awesome Mix" \
    --description "Tracks from my favorite DJ set"
```

### Adjust Detection Settings

For longer tracks (like techno), increase segment step:
```bash
python3 soundcloud_to_spotify.py URL --segment-step 60
```

For denser mixes with quick transitions:
```bash
python3 soundcloud_to_spotify.py URL --segment-step 30
```

### Save & Load Track Lists

Analyzing long mixes takes time. Save your results to skip re-analysis:

```bash
# Save identified tracks to a file
python3 soundcloud_to_spotify.py "URL" --save-tracks tracklists/my_mix.json --name "My Mix"

# Load previously identified tracks (skips Shazam analysis!)
python3 soundcloud_to_spotify.py "URL" --load-tracks tracklists/my_mix.json --name "My Mix"
```

### Analyze Only (No Spotify)

Just identify tracks without creating a playlist:

```bash
python3 soundcloud_to_spotify.py "URL" --analyze-only --save-tracks tracklists/my_mix.json
```

This is useful when:
- You don't have Spotify credentials yet
- Spotify API is having issues
- You just want to see what tracks are in a mix

### All Options

```
positional arguments:
  url                   SoundCloud URL of the mix

options:
  -h, --help            show this help message and exit
  --name, -n            Name for the Spotify playlist
  --description, -d     Description for the Spotify playlist
  --segment-duration    Duration of each segment to analyze (default: 20s)
  --segment-step        Time between segment starts (default: 45s)
  --quiet, -q           Suppress progress output
  --save-tracks, -s     Save identified tracks to a JSON file
  --load-tracks, -l     Load tracks from a JSON file (skip analysis)
  --analyze-only        Only analyze, don't create Spotify playlist
```

## First Run

On first run, your browser will open for Spotify authorization:

1. Log in and click **"Agree"**
2. You'll be redirected to a URL starting with `http://127.0.0.1:8888/callback?code=...`
3. Copy the **entire URL** from your browser's address bar
4. Paste it back into the terminal

The token is cached in `.cache`, so you won't need to do this again unless it expires.

## Example Output

```
📥 Downloading audio from: https://soundcloud.com/artist/mix
✅ Downloaded: /tmp/audio.mp3
🎵 Loading audio file...
⏱️  Duration: 69m 9s
🔍 Analyzing segments (every 45s)...
   [  7.2%] Analyzing at 5:00...
   ✅ Found: Artist - Track Name
   ...

🎉 Identified 18 unique tracks!

🎧 Creating Spotify playlist: [SCF] My Mix
📝 Playlist created: https://open.spotify.com/playlist/...
✅ Added: 15 tracks
❌ Not found: 3 tracks
```

## Tips

- **Processing time**: ~1 minute per 10 minutes of audio
- **Longer mixes**: Use `--segment-step 60` for 1+ hour mixes
- **Dense mixes**: Use `--segment-step 30` if tracks change frequently
- **Private SoundCloud tracks**: Use the secret link (with `/s-XXXXX`)

## Limitations

- Shazam may not identify obscure/unreleased tracks
- Some identified tracks may not be available on Spotify
- Heavily mixed/layered sections might not be identifiable
- Rate limiting may occur with very long mixes (built-in delays help)

## Troubleshooting

### "No tracks were identified"
- The mix may contain mostly unreleased/obscure tracks
- Try with `--segment-step 30` to analyze more frequently

### Spotify authentication error / "Invalid redirect URI"
- Make sure the redirect URI in your Spotify app settings **exactly** matches your `.env` file
- Use `http://127.0.0.1:8888/callback` (not `localhost`, not `https`)
- Delete `.cache` file and try again

### Timeouts during analysis
- This is normal for some segments - the script retries automatically
- If most segments timeout, check your internet connection

### FFmpeg not found
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian  
sudo apt install ffmpeg
```

### Python 3.13 "No module named 'audioop'"
```bash
pip install audioop-lts
```

## Telegram Bot

Share the tool with friends using the Telegram bot! They just send a SoundCloud URL and get a Spotify playlist back.

### Setup

1. **Create a bot** - Message [@BotFather](https://t.me/BotFather) on Telegram:
   ```
   /newbot
   ```
   Follow the prompts and save the token.

2. **Add token to .env**:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   ```

3. **Install dependencies**:
   ```bash
   pip install python-telegram-bot
   ```

4. **Run the bot**:
   ```bash
   python3 telegram_bot.py
   ```

### How It Works

```
Friend: https://soundcloud.com/dj/amazing-mix

Bot: 🎵 Got it! Processing your SoundCloud mix...
     📥 Downloading audio...

Bot: ✅ Downloaded! Starting analysis...
     ⏱️ Duration: 60m 0s
     🔍 Analyzing... (this may take 5 minutes)

Bot: 📊 Progress: 40% (12 tracks found)

Bot: 🎉 Found 28 tracks!
     🎧 Creating Spotify playlist...

Bot: ✅ Playlist created!
     🎧 https://open.spotify.com/playlist/...
     
     📊 Stats:
       • Tracks found: 28
       • Added to Spotify: 25
       • Not on Spotify: 3
```

### Running 24/7

To keep the bot running, you can:
- Use `screen` or `tmux`: `screen -S scfbot python3 telegram_bot.py`
- Deploy to a VPS (DigitalOcean, AWS, etc.)
- Use a service like Railway or Fly.io

## Project Structure

```
scf/
├── soundcloud_to_spotify.py  # Main CLI script
├── telegram_bot.py           # Telegram bot for sharing with friends
├── tracklists/               # Saved track lists (JSON)
├── requirements.txt
└── .env                      # Your credentials (not in git)
```

## License

MIT
