import asyncio
import datetime as dt
import re
import random
import typing as t

import discord
import wavelink
from discord.ext import commands

URL_REGEX = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
OPTIONS = {
    "1️⃣": 0,
    "2⃣": 1,
    "3⃣": 2,
    "4⃣": 3,
    "5⃣": 4,
}
class AlreadyConnectedToChannel(commands.CommandError):
    pass

class NoVoiceChannel(commands.CommandError):
    pass


class QueueIsEmpty(commands.CommandError):
    pass

class NotTracksFound(commands.CommandError):
    pass

class PlayerIsAlreadyPaused(commands.CommandError):
    pass

class PlayerIsAlreadyPlaying(commands.CommandError):
    pass

class NoMoreTracks(commands.CommandError):
    pass

class NoPrevTracks(commands.CommandError):
    pass

class TooHighVolume(commands.CommandError):
    pass

class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0


    @property
    def is_empty(self):
        return not self._queue


    @property
    def first_track(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    @property
    def current_track(self):
        if not self._queue:
            raise QueueIsEmpty
        return self._queue[self.position]

    @property
    def upcoming(self):
        if not self._queue:
            raise QueueIsEmpty
        return self._queue[self.position + 1:]

    @property
    def history(self):
        if not self._queue:
            raise QueueIsEmpty
        return self._queue[:self.position]

    @property
    def five_prev(self):
        tracks = self.history
        titles = []
        str = ""
        i = max(0,len(tracks)-5)
        top = i+5
        while i<top and i<len(tracks):
            titles.append(tracks[i].title)
            i+=1
        if len(titles) != 0:
            for t in titles:
                str = str + t + "\n"
            return str
        else:
            return "No hay canciones previas"

    @property
    def length(self):
        return len(self._queue)

    def add(self, *args):
        self._queue.extend(args)


    def get_next_track(self):
        if not self._queue:
            raise QueueIsEmpty

        self.position = min(self.position+1, len(self._queue))

        if self.position <= len(self._queue) -1:
            return self._queue[self.position]



    def shuffle(self):
        if not self._queue:
            raise QueueIsEmpty

        upcoming = self.upcoming
        random.shuffle(upcoming)

        self._queue = self._queue[:self.position + 1]
        self._queue.extend(upcoming)

    def empty(self):
        self._queue.clear()
        self.position = 0

class Player(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = Queue()

    async def connect(self, ctx, channel=None):
        print("conectando")
        if self.is_connected:
            raise AlreadyConnectedToChannel

        if (channel:= getattr(ctx.author.voice, "channel", channel)) is None:
            raise NoVoiceChannel

        await super().connect(channel.id)
        return channel

    async def teardown(self):
        try:
            await self.destroy()
        except KeyError:
            pass

    async def add_tracks(self, ctx, tracks):
        if not tracks:
            raise NotTracksFound #Si no hay canciones mando error
        if isinstance(tracks, wavelink.TrackPlaylist):
            self.queue.add(*tracks.tracks) #agrego a la cola
        elif len(tracks) == 1:
            self.queue.add(tracks[0])
            await ctx.send(f"agregado {tracks[0].title} a la lista")
        else:
            if (track := await self.choose_track(ctx, tracks)) is not None: #si elijo una cancion de las opciones
                self.queue.add(track) #la agrego
                await ctx.send(f"agregado {track.title} a la lista") #aviso
        if not self.is_playing and not self.queue.is_empty:

             await self.start_playback()
        #Por aca hay un problema
    async def choose_track(self, ctx, tracks):
        def _check(r, u):
            return(
                r.emoji in OPTIONS.keys()
                and u == ctx.author
                and r.message.id == msg.id
            )
        embed = discord.Embed(
            title = "Elegi una cancion",
            description = (
                "\n".join(
                    f"**{i+1}.** {t.title} ({t.length//60000}:{str(t.length%60).zfill(2)})"
                    for i, t in enumerate(tracks[:5])
                )
            ) ,
            color = ctx.author.color,
            timestamp=dt.datetime.utcnow()
        )
        embed.set_author(name="Resultados")
        embed.set_footer(text = f"Pedido por {ctx.author.display_name}", icon_url=ctx.author.avatar_url)

        msg = await ctx.send(embed=embed)
        for emoji in list(OPTIONS.keys())[:min(len(tracks), len(OPTIONS))]:
            await msg.add_reaction(emoji)

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=_check)
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.message.delete() #borra el mensaje del usuario
            return tracks[0]
        else:
            await msg.delete()
            return tracks[OPTIONS[reaction.emoji]]
            #await ctx.message.delete()

    async def start_playback(self):
        await self.play(self.queue.current_track)

    async def advance(self):
        try:
            if(track := self.queue.get_next_track()) is not None:
                await self.play(track)

        except QueueIsEmpty:
            pass

class Music(commands.Cog, wavelink.WavelinkMixin):
    def  __init__(self, bot):
        self.bot = bot
        self.wavelink = wavelink.Client(bot=bot)
        self.bot.loop.create_task(self.start_nodes())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not member.bot and  after.channel is None:
            if not [m for m in before.channel.members if not m.bot]:
                await self.get_player(member.guild).teardown()

    @wavelink.WavelinkMixin.listener()
    async def on_node_ready(self, node):
        print(f"Wavelink node '{node.identifier}' ready.")


    @wavelink.WavelinkMixin.listener("on_track_stuck")
    @wavelink.WavelinkMixin.listener("on_track_end")
    @wavelink.WavelinkMixin.listener("on_track_exception")
    async def on_player_stop(self, node, payload):
        await payload.player.advance()

    async def cog_check(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("Music commands are not available in DMs.")
            return False
        return True

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        nodes = {
            "MAIN" : {
                "host"     : "127.0.0.1",
                "port"     : 2333,
                "rest_uri" :  "http://127.0.0.1:2333",
                "password" :  "youshallnotpass",
                "identifier" : "MAIN",
                "region" :"brazil"
             }
        }
        for node in nodes.values():
            await self.wavelink.initiate_node(**node)

    def get_player(self, obj):
        if isinstance(obj, commands.Context):
            return self.wavelink.get_player(obj.guild.id, cls=Player, Context=obj)
        elif isinstance(obj, discord.Guild):
            return self.wavelink.get_player(obj.id, cls=Player)


    @commands.command(name="connect", aliases=["join"])
    async def connect_command(self, ctx, *, channel: t.Optional[discord.VoiceChannel]):
        player = self.get_player(ctx)
        channel = await player.connect(ctx, channel)
        await player.set_volume(10)
        await ctx.send(f"Conectado a {channel.name}.")


    @connect_command.error
    async def connect_command_error(self, ctx, exc):
        if isinstance(exc, AlreadyConnectedToChannel):
            await ctx.send("Ya estoy conectado a un canal de voz.")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No se encontro el canal de voz.")

    @commands.command(name="disconnect", aliases=["leave"])
    async def disconnect_command(self, ctx):
        player = self.get_player(ctx)
        await player.teardown()
        await ctx.send("Nos re vimos.")

    @commands.command(name="play", aliases=["p"])
    async def play_command(self, ctx, *, query: t.Optional[str]):
        player = self.get_player(ctx)
        if not player.is_connected:
            await player.connect(ctx)
            await player.set_volume(10)


        if query is None:
            if  not player.is_paused and player.is_playing:
                raise PlayerIsAlreadyPlaying

            if player.queue.is_empty:
                raise QueueIsEmpty

            await player.set_pause(False)
        else:
            query = query.strip("<>")
            if not re.match(URL_REGEX, query):
                query = f"ytsearch:{query}"

            await player.add_tracks(ctx, await self.wavelink.get_tracks(query))


    @play_command.error
    async def play_command_error(self, ctx, exc):
        if isinstance(exc, PlayerIsAlreadyPlaying):
            await ctx.send("Ya estoy reproduciendo")
        elif isinstance(exc, QueueIsEmpty):
            await ctx.send("No hay canciones en la lista")
        elif isinstance(exc, NoVoiceChannel):
            await ctx.send("No se encontro el canal de voz.")

    @commands.command(name = "pause")
    async def pause_command(self, ctx):
        player = self.get_player(ctx)

        if  player.is_paused:
            raise PlayerIsAlreadyPaused

        await player.set_pause(True)
        await ctx.send("Musica pausada")


    @pause_command.error
    async def pause_command_error(self, ctx, exc):
        if isinstance(exc, PlayerIsAlreadyPaused):
            await ctx.send("Nada se esta reproduciendo")

    @commands.command(name = "stop")
    async def stop_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.empty()
        await player.stop()
        await ctx.send("F por la musica")

    @commands.command(name="skip")
    async def skip_command(self, ctx):
        player = self.get_player(ctx)
        if not player.queue.upcoming and not player.is_playing:
            raise NoMoreTracks
        if not player.queue.upcoming and player.is_playing:
            await player.stop()

        await ctx.send("Skipeando bro")
        await player.stop()

    @skip_command.error
    async def skip_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No hay canciones en la lista")
        elif isinstance(exc, NoMoreTracks):
            await ctx.send("No hay mas canciones")

    @commands.command(name="prev")
    async def prev_command(self, ctx):
        player = self.get_player(ctx)
        if not player.queue.history:
            raise NoPrevTracks
        if player.is_playing:
            player.queue.position -= 2
            await ctx.send("Volviendo en el tiempo bue")
            await player.stop()
        else:#caso en que ya habia terminado de reproducir todo
            player.queue.position -=1
            await ctx.send("Volviendo en el tiempo bue")
            await player.play(player.queue.current_track)

    @prev_command.error
    async def prev_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No hay canciones en la lista")
        elif isinstance(exc, NoPrevTracks):
            await ctx.send("No hay cancion anterior")

    @commands.command(name="aleatorio")
    async def shuffle_command(self, ctx):
        player = self.get_player(ctx)
        player.queue.shuffle()
        await ctx.send("Randomizando...")

    @shuffle_command.error
    async def shuffle_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No hay canciones en la lista")


    @commands.command(name="volumen", aliases = ["vol", "v"])
    async def volumen_command(self, ctx, vol):
        vol = int(vol)
        if vol > 40:
            raise TooHighVolume
        player = self.get_player(ctx)
        await player.set_volume(vol)

    @volumen_command.error
    async def volumen_command_error(self, ctx, exc):
        if isinstance(exc, TooHighVolume):
            await ctx.send("Re alto bro, calmate un poco")

    @commands.command(name="queue", aliases=["q"])
    async def queue_command(self, ctx, show: t.Optional[int] = 10):
        player = self.get_player(ctx)
        if player.queue.is_empty:
            raise QueueIsEmpty

        if (not player.is_playing) and (not player.queue.upcoming):
            raise NoMoreTracks

        embed = discord.Embed(
            title = "lista",
            color = ctx.author.color,
            timestamp = dt.datetime.utcnow()
        )

        #embed.set_author(name="resultados de la lista")
        embed.add_field(name = "Anteriores", value = player.queue.five_prev, inline = False)
        embed.set_footer(text=f"Pedido por {ctx.author.display_name}", icon_url = ctx.author.avatar_url)
        embed.add_field(name="Reproduciendo actualmente", value=getattr(player.queue.current_track, "title", "No hay mas canciones"), inline=False)
        if upcoming := player.queue.upcoming:
            embed.add_field(
                name = "Siguiente",
                value = "\n".join(t.title for t in upcoming[:show]),
                inline = False
           )
        msg = await ctx.send(embed=embed)

    @queue_command.error
    async def queue_command_error(self, ctx, exc):
        if isinstance(exc, QueueIsEmpty):
            await ctx.send("No hay canciones en la lista")
        if isinstance(exc, NoMoreTracks):
            await ctx.send("No hay proximas canciones")

############################Debug Commands####################################
    @commands.command(name="index", aliases=["idx"])
    async def index_command(self, ctx):
        player = self.get_player(ctx)
        index = player.queue.position
        await ctx.send(f"indice: {index}")



def setup(bot):
    bot.add_cog(Music(bot))
