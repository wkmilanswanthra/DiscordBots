import discord

from discord.ext import commands

client = commands.Bot(command_prefix="!")

@client.command()
async def hello(ctx, arg):
    await ctx.send(arg)


# @client.event
# async def  on_message(message):
#     message.content = message.content.lower()
#     if message.author == client.user:
#         return
#     if message.content.startswith("hello"):
#         await message.channel.get('request-song').send("Hello "+ str(message.author) +", I'm Music Bot")

client.run('OTc0OTU1MTkyOTcxODIxMDk2.GVnjDf.fORta__p4RZ1i6RRYBbl-Ar6WzPsRnaV-TA3mk')