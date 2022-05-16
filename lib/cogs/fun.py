from random import choice

from aiohttp import request
from discord import Embed
from discord.ext.commands import Cog, BucketType
from discord.ext.commands import command, cooldown


class Fun(Cog):
    def __init__(self, bot):
        self.bot = bot

    # command for displaying a hello message
    @command(name="hello", aliases=["hi", "hola", "Hello", "Hi", "Hola"], description="Say Hello to Everything Bot")
    async def hello(self, ctx):
        await ctx.send(
            f"{choice(('Hello', 'Hi', 'Hola'))} {ctx.author.mention} !, {choice(('Looking sharp today', 'Welcome to the server', 'Lets get gaming'))} . " + "\U0001F64B")

    # command for rolling a dice
    @command(name="dice", description="Role a dice to get a random number between 1and 6",
             aliases=["roll", "Dice"])
    async def dice(self, ctx):
        await ctx.send(f"\U0001F3B2 The Dice rolled a {choice(('1', '2', '3', '4', '5', '6'))}")

    # command for tossing a coin
    @command(name="toss", description="Flip a coin",
             aliases=["coin", "flip", "Toss"])
    async def dice(self, ctx):
        await ctx.send(f"\U0001FA99 It is {choice(('Heads', 'Tails',))}")

    # command for generating a random fact
    @command(name="fact", description="Display a random fact ", aliases=["Fact"])
    @cooldown(1, 5, BucketType.user)
    async def fact(self, ctx):
        URL = ["https://some-random-api.ml/facts/dog",
               "https://some-random-api.ml/facts/cat",
               "https://some-random-api.ml/facts/panda",
               "https://some-random-api.ml/facts/koala",
               "https://some-random-api.ml/facts/bird",
               "https://some-random-api.ml/facts/fox", ]

        async with request("GET", choice(URL), headers={}) as response:
            if response.status == 200:
                data = await response.json()
                if data["fact"] is not None:
                    fact = data["fact"]

                embed = Embed(title="\U0001F914 Here is an Interesting Fact !",
                              description=fact,
                              colour=0x5953d7)

                await ctx.send(embed=embed)

    # listener for on_ready state
    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("fun")


def setup(bot):
    bot.add_cog(Fun(bot))
