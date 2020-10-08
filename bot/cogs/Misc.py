from discord.ext import commands
import random
import discord

class Misc(commands.Cog):
    """docstring for Misc."""

    def __init__(self, bot):
        #super(Misc, self).__init__()
        self.bot = bot
        self.conected_users = []
        self.Saludos = ["Saludos invocador", "Q onda?", "Ola", "Holas", "Holanda", "Hello there", "Que onda perro?", "Hello darkness my old friend", "Inserte saludo"]

    @commands.command(name="Hola", aliases=["Saludos", "holanda", "ola", "alo", "holis"])
    async def hola_command(self, ctx):
        saludo = random.choice(self.Saludos)
        await ctx.send(f"{saludo}, {ctx.author.mention}")


def setup(bot):
    bot.add_cog(Misc(bot))
