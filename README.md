# PlainSong
A simple yet powerful Discord music bot that allows users to play songs from YouTube, manage a playlist, and handle caching of downloaded songs with custom cache limits. This bot is built using `discord.py` and `yt-dlp`.

## Features

- Play songs from YouTube using URLs
- Maintain a playlist of songs
- Pause, resume, skip, and replay songs
- Display the current playlist
- Manage a cache of downloaded songs with a custom cache size limit
- Clear cache and metadata

## Prerequisites

- Python 3.8 or higher
- `discord.py` library
- `yt-dlp` library
- `ffmpeg`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Merkycode/PlainSong.git
   cd PlainSong

2. Install the required dependencies:
   ```bash
   pip install discord.py yt-dlp

3: Ensure ffmpeg is installed and available in your system PATH. You can download it from FFmpeg.org.

## Setup
Create a new Discord application and bot account at the Discord Developer Portal.
Copy your bot token and replace YOUR_BOT_TOKEN in bot.py with your actual bot token.

## Usage
1. Run the bot:
   ```bash
   python bot.py

2. Invite the bot to your server using the OAuth2 URL from the Discord Developer Portal.
   
3. Use the following commands in a Discord text channel to interact with the bot:

## Commands
- !join: Makes the bot join the voice channel you are currently in.
- !leave: Makes the bot leave the voice channel.
- !play <YouTube URL>: Plays a song from the provided YouTube URL.
- !pause: Pauses the currently playing song.
- !resume: Resumes the currently paused song.
- !skip: Skips the currently playing song.
- !stop: Stops the bot and clears the queue.
- !volume <volume>: Sets the bot's volume (0-100).
- !playlist: Displays the current song queue.
- !clearCache: Clears the cache and metadata.
- !cacheLimit <size>: Sets the cache limit (e.g., !cacheLimit 5GB).
- !nuke <amount> <unit>: Deletes bot messages from the specified time period (e.g., !nuke 1 hour).

## Example
Here is an example of how to use the bot:

Join a voice channel.
- Type !join in a text channel to make the bot join the voice channel.
- Type !play <YouTube URL> to play a song.
- Use !pause, !resume, !skip, and other commands to control the playback.
