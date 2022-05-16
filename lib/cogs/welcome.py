import discord
from discord.ext.commands import Cog
from discord.ext.commands import command
from discord.utils import get


class Welcome(Cog):
    def __init__(self, bot):
        self.bot = bot

    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("welcome")

    @Cog.listener()
    async def on_member_join(self, member):
        pass

    @Cog.listener()
    async def on_member_remove(self, member):
        pass

    @Cog.listener()
    async def on_raw_reaction_add(self, payload):
        msg_id = payload.message_id
        if msg_id == 975066009293713438:

            if payload.emoji.name == 'radiant':
                role = discord.utils.get(payload.member.guild.roles, name='member')
                if role is not None:
                    member = discord.utils.find(lambda m: m.id == payload.user_id, payload.member.guild.members)
                    if member is not None:
                        await member.add_roles(role)
                        print("User was assigned the role of Member")
                    else:
                        print("Member not Found")
                else:
                    print("Role not Found")
            else:
                channel = payload.member.guild.get_channel(payload.channel_id)
                message = await channel.fetch_message(payload.message_id)
                user = payload.member.guild.get_member(payload.user_id)
                emoji = payload.emoji.name
                await message.remove_reaction(emoji, user)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        msg_id = payload.message_id
        guild = self.bot.get_guild(payload.guild_id)
        if msg_id == 975066009293713438:
            if payload.emoji.name == 'radiant':
                role = discord.utils.get(guild.roles, name='member')

            if role is not None:
                member = discord.utils.find(lambda m: m.id == payload.user_id, guild.members)
                if member is not None:
                    await member.remove_roles(role)
                    print("Member was removed from the users roles")
                else:
                    print("Member not Found")
            else:
                print("Role not Found")


def setup(bot):
    bot.add_cog(Welcome(bot))
