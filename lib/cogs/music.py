from typing import Optional
from datetime import datetime
import discord
from discord import Embed
from discord.ext.commands import Cog
from discord.ext.commands import command


class Music(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("music")


def setup(bot):
    bot.add_cog(Music(bot))
