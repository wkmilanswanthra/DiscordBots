import os
from asyncio import sleep

import discord
from discord import Intents
from glob import glob
from discord import Embed
from random import choice
from webserver import keep_alive

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.errors import HTTPException, Forbidden
from discord.ext.commands import Bot as BotBase
from discord.ext.commands import (CommandNotFound, BadArgument, MissingRequiredArgument, CommandOnCooldown,
                                  when_mentioned_or)



PREFIX = "!"
OWNER_IDS = [727031229085384724]
COGS = [path.split("\\")[-1][:-3] for path in glob("./lib/cogs/*.py")]
IGNORE_EXCEPTIONS = (CommandNotFound, BadArgument)


def get_prefix(bot, message):
    return when_mentioned_or(PREFIX)(bot, message)


class Ready(object):
    def __init__(self):
        for cog in COGS:
            setattr(self, cog, False)

    def ready_up(self, cog):
        setattr(self, cog, True)
        print(f"{cog} cog ready")

    def all_ready(self):
        return all([getattr(self, cog) for cog in COGS])


class Bot(BotBase):
    def __init__(self):
        self.ready = False
        self.cogs_ready = Ready()
        self.guild = None
        self.scheduler = AsyncIOScheduler()
        super().__init__(
            command_prefix=get_prefix,
            owner_ids=OWNER_IDS,
            intents=Intents.all(),
            status=None,
            activity=discord.Activity(type=discord.ActivityType.watching, name="a movie")
        )

    def setup(self):
        for cog in COGS:
            self.load_extension(f"lib.cogs.{cog}")
            print(f"{cog} cog loaded")

        print("Setup is complete")

    def run(self, version):
        self.VERSION = version

        print("Running Setup")
        self.setup()

        # with open("./lib/bot/token.0", "r", encoding="utf-8") as tf:
        #     self.TOKEN = tf.read()

        keep_alive()
        self.TOKEN = os.environ.get('token')

        print("Starting Bot...")
        super().run(self.TOKEN, reconnect=True)

    async def on_connect(self):
        print("Everything Bot is Online")

    async def on_disconnect(self):
        print("Everything Bot is Offline")

    async def on_error(self, err, *args, **kwargs):
        if err == "on_command_error":
            embed = discord.Embed(title="Error",
                                  description="\U0001F635 Something went wrong.\nPlease use the **!help** command to display a list of all commands ",
                                  color=discord.Color.red())
            await args[0].send(embed=embed)

        raise

    async def on_command_error(self, ctx, exc):
        if any([isinstance(exc, error) for error in IGNORE_EXCEPTIONS]):
            pass

        elif isinstance(exc, MissingRequiredArgument):
            embed = discord.Embed(title="", description="😬  One or more required arguments are missing.",
                                  color=discord.Color.red())
            await ctx.send(embed=embed)

        elif isinstance(exc, CommandOnCooldown):

            await ctx.send(
                f"That command is on {str(exc.cooldown.type).split('.')[-1]} cooldown. Try again in {exc.retry_after:,.2f} secs.")

        elif hasattr(exc, "original"):

            # if isinstance(exc.original, HTTPException):

            # 	await ctx.send("Unable to send message.")

            if isinstance(exc.original, Forbidden):
                await ctx.send("\U0001F614	I do not have permission to do that.")

        else:
            raise exc

    async def on_ready(self):
        if not self.ready:

            self.guild = self.get_guild(726645670945095721)
            self.stdout = self.get_channel(975289746202980362)

            while not self.cogs_ready.all_ready():
                await sleep(0.5)

            self.ready = True

            print("Bot is ready")

            if self.stdout is not None:
                await self.stdout.send(
                    "**" + choice(('\U0001F911', '\U0001F92A', '\U0001F929')) + "     Everything Bot is online**")

        else:
            print("Bot Reconnecting...")

    async def on_message(self, message):
        if not message.author.bot:
            await self.process_commands(message)


bot = Bot()
