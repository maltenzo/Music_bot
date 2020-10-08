from pathlib import Path

import discord
from discord.ext import commands

class MusicBot(commands.Bot):
    def __init__(self):
        self._cogs = [p.stem for p in Path(".").glob("./bot/cogs/*.py")]
        super().__init__(command_prefix = self.prefix, case_insensitive = True)

    def setup(self):
        print("corriendo setup")

        for cog in self._cogs:
            self.load_extension(f"bot.cogs.{cog}")
            print(f"Cargado {cog}.")
        print("Setup listo")

    def run(self):
        self.setup()

        with open("data/token.0", "r", encoding="utf-8") as f:
            TOKEN = f.read()

        print("Corriendo bot")
        super().run(TOKEN, reconnect = True)

    async def shutdown(self):
        print("cerrando coneccion con discord")
        await super().close()

    async def close(self):
        print("cerrando por interrupcion de teclado")
        await self.shutdown()

    async def on_connect(self):
        print(f"connected to Discord")

    async def on_resumed(self):
        print("retomando")

    async def on_disconnect(self):
        print("bot desconectado")

    async def on_ready(self):
        self.client_id = (await self.application_info()).id
        print("bot listo")

    async def prefix(self, bot, msg):
        return commands.when_mentioned_or("+")(bot, msg)

    async def process_commands(self, msg):
        ctx = await self.get_context(msg, cls=commands.Context)

        if (ctx.command) is not None:
            await self.invoke(ctx)

    async def on_message(self, msg):
        if not msg.author.bot:
            await self.process_commands(msg)


    async def on_error(self, arr, *args, **kwargs):
        raise

    async def on_command_error(self, ctx, exc):
        raise getattr(exc, "original", exc)    

    # async def on_voice_state_update(self, member,  before, after):
    #     if (before.channel is None) and (after.channel is not None):
    #          for channel in member.guild.text_channels :
    #              if channel.name == "chat":
    #                  await member.guild.system_channel.send(f"Hola {member.mention}, te estabamos esperando bue")
    #     elif (before.channel is not None) and (after.channel is None):
    #              for channel in member.guild.text_channels :
    #                  if channel.name == "chat":
    #                      await member.guild.system_channel.send(f"Nos vemos {member.mention}")
