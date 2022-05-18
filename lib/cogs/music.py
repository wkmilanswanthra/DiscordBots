import asyncio
import itertools
import sys
import traceback
from functools import partial
from typing import Optional
from datetime import datetime
import discord
import youtube_dl
from async_timeout import timeout
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Cog
from discord.ext.commands import command
from youtube_dl import YoutubeDL

youtube_dl.utils.bug_reports_message = lambda: ''

ytdlopts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
    """Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
    """Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.thumbnail = data.get('thumbnail')
        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.duration = data.get('duration')

        # YTDL info dicts (data) have other useful information you might want
        # https://github.com/rg3/youtube-dl/blob/master/README.md

    def __getitem__(self, item: str):
        """Allows us to access attributes similar to a dict.
        This is only useful when you are NOT downloading.
        """
        return self.__getattribute__(item)

    @classmethod
    async def create_source(cls, ctx, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        embed = discord.Embed(title="",
                              description=f"Queued [{data['title']}]({data['webpage_url']}) [{ctx.author.mention}]",
                              color=discord.Color.blue())
        await ctx.send(embed=embed)

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title'], 'thumbnail': data['thumbnails'][0]['url']}

        return cls(discord.FFmpegPCMAudio(source), data=data, requester=ctx.author)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        """Used for preparing a stream, instead of downloading.
        Since Youtube Streaming links expire."""
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(discord.FFmpegPCMAudio(data['url']), data=data, requester=requester)


class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    When the bot disconnects from the Voice it's instance will be destroyed.
    """

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with timeout(300):  # 5 minutes...
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            embed = discord.Embed(title="Now playing",
                                  description=f"**[{source.title}]({source.web_url})** \n\nRequested by [{source.requester.mention}]",
                                  color=discord.Color.green())
            embed.set_thumbnail(url=source.thumbnail)

            self.np = await self._channel.send(embed=embed)
            await self.bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.listening, name=source.title))

            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(Cog):
    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

    def get_player(self, ctx):
        """Retrieve the guild player, or generate one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @command(name="join", aliases=["j", "connect"], description="Join a voice channel for streaming music")
    async def join(self, ctx, *, channel: discord.VoiceChannel = None):
        print("here")
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                print("here 2")
                embed = discord.Embed(title="😬",
                                      description="No channel to join. Please call `!join` from a voice channel.",
                                      color=discord.Color.red())
                await ctx.send(embed=embed)
                raise InvalidVoiceChannel('Invalid voice channel or No available voice channel to join')

        vc = ctx.voice_client

        if vc:
            if vc.channel_id == channel.id:
                return
            try:
                await vc.move_to(channel);
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'connecting channel <{channel}> timed out.')
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                raise VoiceConnectionError(f'connecting channel <{channel} timed out')
        embed = discord.Embed(title="👋  Joined Channel",
                              description=channel,
                              color=discord.Color.green())
        await ctx.send(embed=embed)

    @command(name="leave", aliases=["l", "disconnect"], description="Make everything bot leave the voice channel")
    async def leave(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)
        # if vc.is_playing():
        #     ctx.invoke(self.stop)
        embed = discord.Embed(title="✌️ Leaving Channel", description=vc.channel,
                              color=discord.Color.red())
        await ctx.send(embed=embed)
        await ctx.message.add_reaction('👍')
        await ctx.message.add_reaction('🥲')
        await self.cleanup(ctx.guild)
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="a movie"))

    @command(name="play", aliases=["p"], description="Play a song using a search term or URL")
    async def play(self, ctx, *, search: str):
        """Play a song using a search term or URL"""

        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.join)

        player = self.get_player(ctx)

        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        await ctx.invoke(self.skip)
        await player.queue.put(source)

    # @command(name="add", aliases=["a"], description="Add a song to the queue")
    # async def add_to_queue(self, ctx, *, search: str):
    #     """Play a song using a search term or URL"""
    #
    #     await ctx.trigger_typing()
    #
    #     vc = ctx.voice_client
    #
    #     if not vc:
    #         await ctx.invoke(self.join)
    #
    #     player = self.get_player(ctx)
    #
    #     source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)
    #
    #     await player.queue.put(source)

    @command(name="live", aliases=["li"], description="Play continuous music of a specific genre\n"
                                                      " Types available: chill, party, gaming, ncs, lofi, trap, bass boosted, dub step, techno, house")
    async def live(self, ctx, *, search: Optional[str]):
        """Play continuous music of a specific genre.
         Types available: chill, party, gaming, ncs, lo-fi, trap, bass boosted, dub step, techno, house"""

        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc:
            await ctx.invoke(self.join)

        player = self.get_player(ctx)
        if search is None:
            search = "https://www.youtube.com/watch?v=C9DqEdhDk4A"
        elif search == "chill":
            search = "https://www.youtube.com/watch?v=36YnV9STBqc"
        elif search == "party":
            search = "https://www.youtube.com/watch?v=qWf-FPFmVw0"
        elif search == "lofi" or search == "lo-fi" or search == "lo fi":
            search = "https://www.youtube.com/watch?v=5qap5aO4i9A"
        elif search == "gaming":
            search = "https://www.youtube.com/watch?v=C3Qb6xAovSk"
        elif search == "ncs":
            search = "https://www.youtube.com/watch?v=7tNtU5XFwrU"
        elif search == "trap":
            search = "https://www.youtube.com/watch?v=6Qq2OMFh8Pc"
        elif search == "dubstep" or search == "dub step" or search == "dub-step":
            search = "https://www.youtube.com/watch?v=o8LyCavr-X8"
        elif search == "house" or search == "techno" or search == "deep house":
            search = "https://www.youtube.com/watch?v=thd6h-ZZIfo"
        elif search == "bass boosted":
            search = "https://www.youtube.com/watch?v=FM6MKgVcfyo"
        else:
            search = search + "24/7 live music"
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

        await ctx.invoke(self.skip)
        await player.queue.put(source)

    @command(name="pause", aliases=["pa"], description="Pauses the currently playing song")
    async def pause(self, ctx):
        """Pause the currently playing song."""

        vc = ctx.voice_client

        if not vc or not vc.is_playing():
            embed = discord.Embed(title="", description="Eh 🤨  I am currently not playing anything",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)
        elif vc.is_paused():
            return

        vc.pause()
        await ctx.send("⏸ Paused")

    @command(name="resume", description="Resume the currently paused song", aliases=["r"])
    async def resume(self, ctx):
        """Resume the currently paused song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)
        elif not vc.is_paused():
            return

        vc.resume()
        await ctx.send("⏯ Resuming")

    @command(name="skip", description="Skip to the next song in the queue", aliases=['next', 'skp', 'sk'])
    async def skip(self, ctx):
        """skip the song"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬 I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        if vc.is_paused():
            pass
        elif not vc.is_playing():
            return

        vc.stop()

    @command(name="volume", description="Control the volume of the bot", aliases=["v", "sound"])
    async def volume(self, ctx, *, vol: float = None):
        """change the player volume"""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        if not vol:
            embed = discord.Embed(title="", description=f"🔊 **{vc.source.volume * 100}%**",
                                  color=discord.Color.green())
            return await ctx.send(embed=embed)

        if not 0 < vol < 201:
            embed = discord.Embed(title="", description="😬 Please enter a value between 1 and 100",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        player = self.get_player(ctx)

        if vc.source:
            vc.source.volume = vol / 100

        player.volume = vol / 100
        embed = discord.Embed(title="", description=f'🔊  **`{vol}`**  set the volume to **{vc.source.volume * 100}%**',
                              color=discord.Color.green())
        await ctx.send(embed=embed)

    @command(name="now playing", aliases=["np", "current", 'currentsong', 'playing', 'song'],
             description="Display the currently playing song")
    async def now_playing(self, ctx):
        """Display information about the currently playing song."""
        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        player = self.get_player(ctx)
        if not player.current:
            embed = discord.Embed(title="", description="😬 I am currently not playing anything",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        seconds = vc.source.duration % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        embed = discord.Embed(title="Now Playing",
                              description=f"**[{vc.source.title}]({vc.source.web_url})** \n[{vc.source.requester.mention}] | `{duration}`",
                              color=discord.Color.green())
        embed.set_thumbnail(url=vc.source.thumbnail)

        await ctx.send(embed=embed)

    @command(name="queue", aliases=["q", "list", "playlist"], description="Display the current queue")
    async def queue(self, ctx, *, song: Optional[str]):
        """Retrieve the current queue"""
        await ctx.trigger_typing()

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        player = self.get_player(ctx)

        if song is not None:
            source = await YTDLSource.create_source(ctx, song, loop=self.bot.loop, download=False)
            return await player.queue.put(source)

        if player.queue.empty():
            embed = discord.Embed(title="", description="😬 Queue is empty", color=discord.Color.red())
            return await ctx.send(embed=embed)

        seconds = vc.source.duration % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            duration = "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            duration = "%02dm %02ds" % (minutes, seconds)

        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        fmt = '\n'.join(
            f"`{(upcoming.index(_)) + 1}.` [{_['title']}]({_['webpage_url']}) | ` {duration} Requested by: "
            f"{_['requester']}`\n"
            for _ in upcoming)
        fmt = f"\n**Now Playing:**\n[{vc.source.title}]({vc.source.web_url}) | ` {duration} Requested by: {vc.source.requester}`\n\n\n**Up Next:**\n\n" + fmt + f"\n**{len(upcoming)} songs in queue**"
        embed = discord.Embed(title=f'Queue for {ctx.guild.name}', description=fmt, color=discord.Color.blue())
        embed.set_footer(text=f"{ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(name='remove', aliases=['rm', 'rem', 'del'], description="removes specified song from queue")
    async def remove_(self, ctx, pos: int = None):
        """Removes specified song from queue"""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="😬  I'm not connected to a voice channel",
                                  color=discord.Color.red())
            return await ctx.send(embed=embed)

        player = self.get_player(ctx)
        if pos == None:
            player.queue._queue.pop()
        else:
            try:
                s = player.queue._queue[pos - 1]
                del player.queue._queue[pos - 1]
                embed = discord.Embed(title="",
                                      description=f"Removed [{s['title']}]({s['webpage_url']}) [{s['requester'].mention}]",
                                      color=discord.Color.green())
                await ctx.send(embed=embed)
            except:
                embed = discord.Embed(title="", description=f'😬  Could not find a track for "{pos}"',
                                      color=discord.Color.green())
                await ctx.send(embed=embed)

    @commands.command(name='clear', aliases=['clr', 'cl', 'cr'], description="clears entire queue")
    async def clear_(self, ctx):
        """Deletes entire queue of upcoming songs."""

        vc = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = discord.Embed(title="", description="I'm not connected to a voice channel",
                                  color=discord.Color.green())
            return await ctx.send(embed=embed)

        player = self.get_player(ctx)
        player.queue._queue.clear()
        await ctx.send('**Cleared**')

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("music")


def setup(bot):
    bot.add_cog(Music(bot))
