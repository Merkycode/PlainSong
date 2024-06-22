import discord
from discord.ext import commands
import asyncio
import logging
import subprocess
import json
import os
import re
import shutil
from datetime import datetime, timedelta

logging.basicConfig(level=logging.DEBUG)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

joined_user = None
inactive_timer = None
song_queue = asyncio.Queue()
currently_playing = None  # Track the currently playing song
played_songs = []  # List to store previously played songs
cache_dir = 'cache'
metadata_file = os.path.join(cache_dir, 'metadata.json')
cache_limit_file = os.path.join(cache_dir, 'cache_limit.txt')

# Set default cache limit to 5GB
default_cache_limit = 5 * 1024 * 1024 * 1024  # 5GB in bytes

if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

if not os.path.exists(metadata_file):
    with open(metadata_file, 'w') as f:
        json.dump({}, f)

if not os.path.exists(cache_limit_file):
    with open(cache_limit_file, 'w') as f:
        f.write(str(default_cache_limit))

# Embed color
EMBED_COLOR = 0x1ABC9C

class MusicControls(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="Play/Pause", style=discord.ButtonStyle.primary, emoji="⏯️")
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.ctx.voice_client
        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Paused the song", ephemeral=True)
        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Resumed the song", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, emoji="⏩")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = self.ctx.voice_client
        if voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("Skipped the song", ephemeral=True)

    @discord.ui.button(label="Replay", style=discord.ButtonStyle.primary, emoji="🔄")
    async def replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Replaying the song", ephemeral=True)
        await replay_song(self.ctx, interaction.message.embeds[0].title)

@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} is now online!')

@bot.command(name="join", help="Tells the bot to join the voice channel")
async def join(ctx):
    global joined_user
    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
        return
    else:
        channel = ctx.message.author.voice.channel
        await channel.connect()
        joined_user = ctx.message.author
        await ctx.send(f"Joined {channel} at the request of {joined_user.name}")
        start_inactivity_timer(ctx)

@bot.command(name="leave", help="To make the bot leave the voice channel")
async def leave(ctx):
    global joined_user
    if ctx.message.author != joined_user:
        await ctx.send(f"Only {joined_user.name} can make the bot leave the voice channel")
        return

    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send(f"Left the voice channel as requested by {joined_user.name}")
    else:
        await ctx.send("The bot is not connected to a voice channel.")

def start_inactivity_timer(ctx):
    global inactive_timer
    if inactive_timer:
        inactive_timer.cancel()
    
    inactive_timer = bot.loop.create_task(check_inactivity(ctx))

async def check_inactivity(ctx):
    await asyncio.sleep(300)  # 5 minutes
    voice_client = ctx.message.guild.voice_client
    if voice_client and not voice_client.is_playing():
        await voice_client.disconnect()
        await ctx.send("Bot has left the voice channel due to inactivity.")

def extract_video_id(url):
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
    return video_id_match.group(1) if video_id_match else None

def load_metadata():
    with open(metadata_file, 'r') as f:
        return json.load(f)

def save_metadata(metadata):
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=4)

def get_cache_limit():
    with open(cache_limit_file, 'r') as f:
        return int(f.read())

def set_cache_limit(limit):
    with open(cache_limit_file, 'w') as f:
        f.write(str(limit))

def get_cache_size():
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(cache_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

async def enforce_cache_limit():
    cache_limit = get_cache_limit()
    while get_cache_size() > cache_limit:
        await remove_oldest_file()

async def remove_oldest_file():
    metadata = load_metadata()
    files = [(os.path.getctime(os.path.join(cache_dir, f)), f) for f in os.listdir(cache_dir) if f.endswith('.mp3')]
    if files:
        oldest_file = min(files)[1]
        file_path = os.path.join(cache_dir, oldest_file)
        while currently_playing and currently_playing['file'] == file_path:
            await asyncio.sleep(1)  # Wait until the currently playing file is not in use
        os.remove(file_path)
        video_id = os.path.splitext(oldest_file)[0]
        if video_id in metadata:
            del metadata[video_id]
            save_metadata(metadata)

async def prepare_song(url):
    metadata = load_metadata()
    video_id = extract_video_id(url)
    if video_id and video_id in metadata:
        return metadata[video_id]

    process = await asyncio.create_subprocess_exec(
        'python', 'worker.py', url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Worker process failed: {stderr.decode()}")
    song_info = json.loads(stdout)
    metadata[video_id] = song_info
    save_metadata(metadata)
    await enforce_cache_limit()
    return song_info

@bot.command(name="play", help="To play a song from a YouTube URL")
async def play(ctx, url):
    global joined_user
    global inactive_timer
    global currently_playing

    await ctx.message.delete()  # Delete the user's message

    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
        return

    if ctx.voice_client is None:
        channel = ctx.message.author.voice.channel
        await channel.connect()
        joined_user = ctx.message.author
        await ctx.send(f"Joined {channel} at the request of {joined_user.name}")

    try:
        # Prepare the song immediately and add the song info to the queue
        song_info = await prepare_song(url)
        await song_queue.put(song_info)
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next_song(ctx)
        else:
            currently_playing = song_info

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")
        logging.error(f"Error occurred: {str(e)}")

async def play_next_song(ctx):
    global currently_playing
    if not song_queue.empty():
        next_song_info = await song_queue.get()
        currently_playing = next_song_info
        ctx.voice_client.play(discord.FFmpegPCMAudio(next_song_info['file']), after=lambda e: bot.loop.create_task(play_next_song(ctx)))
        embed_message = await ctx.send(embed=create_embed(next_song_info, "Now playing"), view=MusicControls(ctx))
        start_inactivity_timer(ctx)

async def replay_song(ctx, title):
    global currently_playing
    metadata = load_metadata()
    for video_id, song in metadata.items():
        if song['title'] == title:
            currently_playing = song
            ctx.voice_client.stop()
            ctx.voice_client.play(discord.FFmpegPCMAudio(song['file']), after=lambda e: bot.loop.create_task(play_next_song(ctx)))
            embed_message = await ctx.send(embed=create_embed(song, "Replaying"), view=MusicControls(ctx))
            start_inactivity_timer(ctx)
            return
    await ctx.send("Song not found in cache.")

def create_embed(song_info, description):
    embed = discord.Embed(title=song_info['title'], url=song_info['webpage_url'], description=description, color=EMBED_COLOR)
    embed.add_field(name="Duration", value=f"{song_info['duration']} seconds")
    embed.set_thumbnail(url=song_info['thumbnail'])
    return embed

async def get_song_list():
    return list(song_queue._queue)

@bot.command(name="playlist", help="Displays the current song queue")
async def playlist(ctx):
    song_list = await get_song_list()
    if not song_list:
        await ctx.send("The playlist is currently empty.")
        return

    embed = discord.Embed(title="Current Playlist", color=EMBED_COLOR)
    for idx, song in enumerate(song_list, start=1):
        embed.add_field(name=f"Song {idx}", value=f"[{song['title']}]({song['webpage_url']})", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="clearCache", help="Clears the cache and metadata")
async def clear_cache(ctx):
    shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)
    with open(metadata_file, 'w') as f:
        json.dump({}, f)
    with open(cache_limit_file, 'w') as f:
        f.write(str(default_cache_limit))
    await ctx.send("Cache and metadata cleared.")

@bot.command(name="cacheLimit", help="Sets the cache limit (e.g., !cacheLimit 5GB)")
async def cache_limit(ctx, limit: str):
    size_units = {'kb': 1024, 'mb': 1024 ** 2, 'gb': 1024 ** 3}
    size_regex = re.match(r'(\d+)(kb|mb|gb)', limit.lower())
    if not size_regex:
        await ctx.send("Invalid size format. Use format like 5GB, 500MB, etc.")
        return

    size_value, size_unit = size_regex.groups()
    cache_limit = int(size_value) * size_units[size_unit]
    set_cache_limit(cache_limit)
    await enforce_cache_limit()
    await ctx.send(f"Cache limit set to {limit.upper()}.")

@bot.command(name="pause", help="Pauses the current song")
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the song")

@bot.command(name="resume", help="Resumes the current song")
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the song")

@bot.command(name="skip", help="Skips the current song")
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the song")

@bot.command(name="stop", help="Stops the bot and clears the queue")
async def stop(ctx):
    while not song_queue.empty():
        await song_queue.get()
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    await ctx.send("Stopped the music and cleared the queue")

@bot.command(name="volume", help="Sets the volume of the bot")
async def volume(ctx, volume: int):
    if ctx.voice_client.source:  
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Set the volume to {volume}%")

@bot.command(name="nuke", help="Deletes bot messages from the specified time period")
async def nuke(ctx, amount: int, unit: str):
    units = {"minute": 1, "minutes": 1, "hour": 60, "hours": 60, "day": 1440, "days": 1440, "week": 10080, "weeks": 10080}
    if unit not in units:
        await ctx.send("Invalid time unit. Use minutes, hours, days, or weeks.")
        return

    delta = timedelta(minutes=amount * units[unit])
    cutoff = datetime.utcnow() - delta

    deleted = 0
    async for message in ctx.channel.history(limit=None, after=cutoff):
        if message.author == bot.user:
            await message.delete()
            deleted += 1
            await asyncio.sleep(1)  # Add a delay to prevent rate limiting

    await ctx.send(f"Deleted {deleted} messages sent by the bot in the last {amount} {unit}(s).")

bot.run("App Token")
