# SoundCloud to Spotify Toolkit

A collection of tools for working with SoundCloud and Spotify.

## Tools

### 1. SoundCloud Mix Converter (`converter/`)
Identify songs in a SoundCloud mix using Shazam and create a Spotify playlist.

```bash
./venv/bin/python3 converter/soundcloud_to_spotify.py "https://soundcloud.com/artist/mix"
```

### 2. Telegram Bot (`bot/`)
Share the converter with friends via Telegram.

```bash
./venv/bin/python3 bot/telegram_bot.py
```

### 3. Common Likes Finder (`common_likes/`)
Find tracks that multiple SoundCloud artists have liked in common.

```bash
./venv/bin/python3 common_likes/common_likes.py janefitz bobbypleasureclub chezdemilo
```

### 4. Discogs to Spotify (`discogs_finder/`)
Scrape a Discogs seller's inventory and create a Spotify playlist from matching releases.

```bash
./venv/bin/python3 discogs_finder/discogs_to_spotify.py "https://www.discogs.com/seller/houseofdog/profile" --name "House of Dog Records"
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/cprkrn/spopify.git
cd spopify

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Setup

### Spotify Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app with redirect URI: `http://127.0.0.1:8888/callback`
3. Create `.env` file:

```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

### Telegram Bot (Optional)

1. Message [@BotFather](https://t.me/BotFather) to create a bot
2. Add to `.env`:
```
TELEGRAM_BOT_TOKEN=your_token
```

---

## Project Structure

```
scf/
├── converter/                  # SoundCloud → Spotify converter
│   └── soundcloud_to_spotify.py
├── bot/                        # Telegram bot
│   └── telegram_bot.py
├── common_likes/               # Find common likes between artists
│   ├── common_likes.py
│   └── create_soundcloud_playlist.py
├── discogs_finder/             # Discogs → Spotify finder
│   └── discogs_to_spotify.py
├── tracklists/                 # Saved track lists (JSON)
├── requirements.txt
└── .env                        # Your credentials (not in git)
```

## License

MIT
