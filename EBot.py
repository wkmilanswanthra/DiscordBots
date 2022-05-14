import discord

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print("Everything Bot is Online")


@client.event
async def on_raw_reaction_add(payload):
    msg_id = payload.message_id
    if msg_id == 975066009293713438:
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, client.guilds)

        if payload.emoji.name == 'radiant':
            role = discord.utils.get(guild.roles, name='member')
            if role is not None:
                member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
                if member is not None:
                    await member.add_roles(role)
                    print("User was assigned the role of Member")
                else:
                    print("Member not Found")
            else:
                print("Role not Found")
        else:
            channel = client.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            user = client.get_user(payload.user_id)
            emoji = payload.emoji.name
            await message.remove_reaction(emoji, user)


@client.event
async def on_raw_reaction_remove(payload):
    msg_id = payload.message_id
    if msg_id == 975066009293713438:
        guild_id = payload.guild_id
        guild = discord.utils.find(lambda g: g.id == guild_id, client.guilds)
        print("here")
        if payload.emoji.name == 'radiant':
            role = discord.utils.get(guild.roles, name='member')
            print("here2")

        if role is not None:
            member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
            if member is not None:
                await member.remove_roles(role)
                print("Member was removed from the users roles")
            else:
                print("Member not Found")
        else:
            print("Role not Found")


# @client.event
# async def  on_message(message):
#     message.content = message.content.lower()
#     if message.author == client.user:
#         return
#     if message.content.startswith("hello"):
#         await message.channel.get('request-song').send("Hello "+ str(message.author) +", I'm Music Bot")

client.run('OTc1MDAwODM4MzU3NTQ5MDU2.GXXRqP.m5FRnuO-FmV6sLqTtuPCuHX5F_0DWUu-IjY2a8')
