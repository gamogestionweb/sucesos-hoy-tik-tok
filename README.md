# Sucesos Hoy TikTok Bot

Automated bot to monitor Madrid emergencies and publish to TikTok.

## Features

- Monitors @EmergenciasMad Twitter/X account in real-time
- Automatically downloads videos from tweets
- Video editing:
  - Random segment selection
  - Vertical 9:16 format conversion (no black bars, zoom/crop)
  - Centered text overlay with the news
  - Spanish TTS voice narrating the news
- Automatic text reformulation (same news, different words)
- Converts @mentions to readable text (e.g., @BomberosMad -> Bomberos de Madrid)
- Removes # from hashtags but keeps the content
- Automatic TikTok publishing

## Requirements

- Python 3.10+
- FFmpeg installed and in PATH
- Twitter Developer account (API keys)
- TikTok account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gamogestionweb/sucesos-hoy-tik-tok.git
cd sucesos-hoy-tik-tok
```

2. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. Install FFmpeg:
   - Windows: Download from https://ffmpeg.org/download.html and add to PATH
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`

## Usage

### Run the bot (continuous monitoring):
```bash
python bot.py
```

### Test with a specific tweet:
```bash
python test_tweet.py
```
Edit the TWEET_URL variable in the file to test different tweets.

## Project Structure

```
sucesos-bot/
├── bot.py              # Main bot with continuous monitoring
├── test_tweet.py       # Test script for individual tweets
├── requirements.txt    # Python dependencies
├── .env.example        # Configuration template
├── .gitignore
└── src/
    ├── config.py           # Configuration loader
    ├── twitter_api.py      # Twitter v2 API connection
    ├── twitter_monitor.py  # Account monitoring
    ├── video_downloader.py # Video download with yt-dlp
    ├── video_editor.py     # FFmpeg video editing
    ├── text_rewriter.py    # Text reformulation
    ├── tts_generator.py    # Voice generation (edge-tts)
    └── tiktok_uploader.py  # TikTok upload (Playwright)
```

## Configuration

| Variable | Description |
|----------|-------------|
| TWITTER_USERNAME | Twitter account to monitor |
| TWITTER_BEARER_TOKEN | Twitter API Bearer Token |
| CHECK_INTERVAL | Check interval in seconds |
| MAX_CLIP_DURATION | Maximum clip duration (seconds) |
| MIN_CLIP_DURATION | Minimum clip duration (seconds) |

## How It Works

1. **Monitoring**: The bot checks @EmergenciasMad every 1-60 minutes (randomized to avoid detection)
2. **Download**: When a new tweet with video is detected, it downloads using yt-dlp
3. **Processing**: 
   - Selects a random segment (15-60 seconds)
   - Converts to vertical 9:16 format (crops/zooms to fill screen)
   - Generates TTS audio in Spanish
   - Overlays centered text with the news
4. **Reformulation**: Rewrites the news text keeping proper names but changing verbs/nouns
5. **Publishing**: Uploads to TikTok using Playwright browser automation

## License

MIT License

