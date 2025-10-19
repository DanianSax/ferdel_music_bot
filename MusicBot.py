# Importing libraries and modules
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp # NEW
from collections import deque # NEW
import asyncio # NEW

# Environment variables for tokens and other sensitive data
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}

# Diccionario para controlar el modo de bucle para cada servidor
# Valores posibles: "none", "song", "queue"
LOOP_MODES = {}

# Diccionario para controlar si las recomendaciones están activadas para cada servidor
RECOMMENDATIONS_ENABLED = {}

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

# Función para extraer información de una sola canción
async def extract_single_song(url, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract_single(url, ydl_opts))

def _extract_single(url, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

# Función para obtener recomendaciones basadas en una canción
async def get_recommendations(voice_client, guild_id, channel, query):
    # Opciones para yt-dlp
    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": False,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "extractor_args": {
            "youtube": {
                "formats": "missing_pot"
            }
        }
    }
    
    # Buscar recomendaciones (usando la búsqueda de YouTube con el título de la canción)
    search_query = f"ytsearch5: {query} similar songs"
    try:
        results = await search_ytdlp_async(search_query, ydl_options)
        tracks = results.get("entries", [])
        
        if not tracks:
            await channel.send("No se encontraron recomendaciones.")
            return
        
        # Crear la cola si no existe
        if SONG_QUEUES.get(guild_id) is None:
            SONG_QUEUES[guild_id] = deque()
        
        # Añadir recomendaciones a la cola
        added_count = 0
        for track in tracks:
            if track:
                audio_url = track.get("url")
                title = track.get("title", "Untitled")
                if audio_url:
                    SONG_QUEUES[guild_id].append((audio_url, title))
                    added_count += 1
        
        # Informar al usuario
        if added_count > 0:
            await channel.send(f"Se han añadido {added_count} recomendaciones a la cola.")
            
            # Guardar la última canción reproducida para futuras recomendaciones
            voice_client.last_played = query
            
            # Iniciar la reproducción
            await play_next_song(voice_client, guild_id, channel)
        else:
            await channel.send("No se pudieron añadir recomendaciones a la cola.")
    
    except Exception as e:
        print(f"Error al obtener recomendaciones: {e}")
        await channel.send("Ocurrió un error al buscar recomendaciones.")


# Setup of intents. Intents are permissions the bot has on the server
intents = discord.Intents.default()
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Bot ready-up code
@bot.event
async def on_ready():
    # Sincronización automática de comandos al iniciar el bot
    try:
        commands = await bot.tree.sync()
        print(f"Sincronizados {len(commands)} comandos automáticamente")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")
    print(f"{bot.user} is online!")

@bot.event
async def on_reaction_add(reaction, user):
    # Ignorar las reacciones del propio bot
    if user.bot:
        return
    
    # Verificar que la reacción sea en un mensaje del bot
    if reaction.message.author.id != bot.user.id:
        return
    
    # Obtener el cliente de voz para el servidor
    guild = reaction.message.guild
    voice_client = guild.voice_client
    guild_id = str(guild.id)
    
    # Verificar que el bot esté conectado a un canal de voz
    if not voice_client:
        return
    
    # Manejar diferentes reacciones
    emoji = str(reaction.emoji)
    
    if emoji == "⏯️":  # Play/Pause
        if voice_client.is_playing():
            voice_client.pause()
            await reaction.message.channel.send("Reproducción pausada.")
        elif voice_client.is_paused():
            voice_client.resume()
            await reaction.message.channel.send("Reproducción reanudada.")
    
    elif emoji == "⏭️":  # Skip
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
            await reaction.message.channel.send("Saltando a la siguiente canción.")
    
    elif emoji == "🔁":  # Loop
        # Cambiar el modo de bucle cíclicamente: none -> song -> queue -> none
        current_mode = LOOP_MODES.get(guild_id, "none")
        
        if current_mode == "none":
            LOOP_MODES[guild_id] = "song"
            await reaction.message.channel.send("Modo de bucle: Repetir canción actual.")
        elif current_mode == "song":
            LOOP_MODES[guild_id] = "queue"
            await reaction.message.channel.send("Modo de bucle: Repetir toda la cola.")
        else:
            LOOP_MODES[guild_id] = "none"
            await reaction.message.channel.send("Modo de bucle desactivado.")
    
    elif emoji == "🔀":  # Shuffle
        if guild_id in SONG_QUEUES and len(SONG_QUEUES[guild_id]) > 1:
            # Mezclar la cola (excepto la canción actual si está reproduciéndose)
            import random
            queue_list = list(SONG_QUEUES[guild_id])
            if voice_client.is_playing() or voice_client.is_paused():
                current_song = queue_list[0]
                remaining_songs = queue_list[1:]
                random.shuffle(remaining_songs)
                SONG_QUEUES[guild_id] = deque([current_song] + remaining_songs)
            else:
                random.shuffle(queue_list)
                SONG_QUEUES[guild_id] = deque(queue_list)
            await reaction.message.channel.send("Cola mezclada aleatoriamente.")
        else:
            await reaction.message.channel.send("No hay suficientes canciones en la cola para mezclar.")
    
    elif emoji == "⏹️":  # Stop
        if voice_client.is_connected():
            # Limpiar la cola
            if guild_id in SONG_QUEUES:
                SONG_QUEUES[guild_id].clear()
            
            # Detener la reproducción
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
            
            # Desconectar
            await voice_client.disconnect()
            await reaction.message.channel.send("Reproducción detenida y bot desconectado.")
    
    elif emoji == "📋":  # Queue
        if guild_id in SONG_QUEUES and SONG_QUEUES[guild_id]:
            queue_list = list(SONG_QUEUES[guild_id])
            
            # Crear un mensaje con la lista de canciones en cola
            message = "**Cola de reproducción:**\n"
            for i, (_, title) in enumerate(queue_list, 1):
                message += f"{i}. {title}\n"
                # Limitar el mensaje a 20 canciones para evitar mensajes muy largos
                if i >= 20 and len(queue_list) > 20:
                    message += f"... y {len(queue_list) - 20} canciones más."
                    break
            
            await reaction.message.channel.send(message)
        else:
            await reaction.message.channel.send("La cola de reproducción está vacía.")


@bot.tree.command(name="skip", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")


@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if something is actually playing
    if not voice_client.is_playing():
        return await interaction.response.send_message("Nothing is currently playing.")
    
    # Pause the track
    voice_client.pause()
    await interaction.response.send_message("Playback paused!")


@bot.tree.command(name="resume", description="Resume the currently paused song.")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await interaction.response.send_message("I'm not in a voice channel.")

    # Check if it's actually paused
    if not voice_client.is_paused():
        return await interaction.response.send_message("I’m not paused right now.")
    
    # Resume playback
    voice_client.resume()
    await interaction.response.send_message("Playback resumed!")


@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    # Check if the bot is in a voice channel
    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("I'm not connected to any voice channel.")

    # Clear the guild's queue
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    # If something is playing or paused, stop it
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    # (Optional) Disconnect from the channel
    await voice_client.disconnect()

    await interaction.response.send_message("Stopped playback and disconnected!")


@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel

    if voice_channel is None:
        await interaction.followup.send("You must be in a voice channel.")
        return

    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
        # Iniciar la tarea de verificación de usuarios en el canal
        asyncio.create_task(check_voice_channel(voice_client))
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": False,  # Permitir listas de reproducción
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "extractor_args": {
            "youtube": {
                "formats": "missing_pot"
            }
        }
    }

    # Detectar si es una URL directa o una búsqueda
    if song_query.startswith(('https://', 'http://', 'www.')):
        query = song_query  # URL directa
        results = await search_ytdlp_async(query, ydl_options)
        
        # Verificar si es una lista de reproducción
        if 'entries' in results:
            # Es una lista de reproducción
            tracks = results['entries']
            playlist_title = results.get('title', 'Playlist')
            
            # Crear la cola si no existe
            guild_id = str(interaction.guild_id)
            if SONG_QUEUES.get(guild_id) is None:
                SONG_QUEUES[guild_id] = deque()
            
            # Procesar el primer tema inmediatamente si está disponible
            first_track_processed = False
            added_count = 0
            
            for i, track in enumerate(tracks):
                if track:
                    audio_url = track.get("url")
                    title = track.get("title", "Untitled")
                    if audio_url:
                        # Si es el primer tema y no hay nada reproduciéndose, reproducirlo inmediatamente
                        if i == 0 and not (voice_client.is_playing() or voice_client.is_paused()):
                            # En lugar de reproducir directamente, añadir a la cola y usar play_next_song
                            SONG_QUEUES[guild_id].appendleft((audio_url, title))
                            await play_next_song(voice_client, guild_id, interaction.channel)
                            first_track_processed = True
                            
                            # Iniciar la tarea de verificación de canal de voz si no está ya en ejecución
                            if not hasattr(voice_client, 'check_voice_channel_task') or voice_client.check_voice_channel_task.done():
                                voice_client.check_voice_channel_task = asyncio.create_task(check_voice_channel(voice_client))
                        else:
                            # Añadir el resto de temas a la cola
                            SONG_QUEUES[guild_id].append((audio_url, title))
                        
                        added_count += 1
            
            # Informar al usuario sobre la lista de reproducción
            await interaction.followup.send(f"Added {added_count} songs from playlist **{playlist_title}** to the queue.")
            
            # Si no se procesó el primer tema (porque ya había algo reproduciéndose), asegurarse de que haya algo en reproducción
            if not first_track_processed and not (voice_client.is_playing() or voice_client.is_paused()) and SONG_QUEUES[guild_id]:
                await play_next_song(voice_client, guild_id, interaction.channel)
            
            return
        else:
            # Es un solo video
            tracks = [results] if results else []
    else:
        query = "ytsearch1: " + song_query  # Búsqueda de texto
        results = await search_ytdlp_async(query, ydl_options)
        tracks = results.get("entries", [])

    if tracks is None:
        await interaction.followup.send("No results found.")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)


async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()
        
        # Verificar el modo de bucle
        if guild_id in LOOP_MODES:
            # Si está en modo bucle de canción, volver a añadir la misma canción al principio
            if LOOP_MODES[guild_id] == "song":
                SONG_QUEUES[guild_id].appendleft((audio_url, title))
            # Si está en modo bucle de cola, añadir la canción al final
            elif LOOP_MODES[guild_id] == "queue":
                SONG_QUEUES[guild_id].append((audio_url, title))

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
            # Remove executable if FFmpeg is in PATH
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="bin\\ffmpeg\\ffmpeg.exe")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)
        # Enviar mensaje con controles de reacción
        message = await channel.send(f"Now playing: **{title}**")
        # Añadir reacciones para control
        control_reactions = ["⏯️", "⏭️", "🔁", "🔀", "⏹️", "📋"]
        for reaction in control_reactions:
            await message.add_reaction(reaction)
        
        # Guardar la última canción reproducida para recomendaciones
        voice_client.last_played = title
    else:
        # Verificar si hay recomendaciones activadas para este servidor
        if guild_id in RECOMMENDATIONS_ENABLED and RECOMMENDATIONS_ENABLED[guild_id]:
            # Buscar la última canción reproducida para generar recomendaciones
            if hasattr(voice_client, "last_played") and voice_client.last_played:
                last_title = voice_client.last_played
                await channel.send(f"La cola ha terminado. Buscando recomendaciones basadas en: **{last_title}**")
                
                # Buscar recomendaciones
                await get_recommendations(voice_client, guild_id, channel, last_title)
            else:
                # Si no hay historial, programar desconexión
                if not hasattr(voice_client, "disconnect_task") or voice_client.disconnect_task.done():
                    voice_client.disconnect_task = asyncio.create_task(disconnect_after_timeout(voice_client, 300))
        else:
            # En lugar de desconectar inmediatamente, programamos una desconexión después de 5 minutos
            if not hasattr(voice_client, "disconnect_task") or voice_client.disconnect_task.done():
                voice_client.disconnect_task = asyncio.create_task(disconnect_after_timeout(voice_client, 300))  # 300 segundos = 5 minutos
        
        SONG_QUEUES[guild_id] = deque()

async def disconnect_after_timeout(voice_client, timeout):
    try:
        await asyncio.sleep(timeout)
        if voice_client.is_connected() and not voice_client.is_playing():
            await voice_client.disconnect()
            print(f"Bot desconectado después de {timeout} segundos de inactividad")
    except asyncio.CancelledError:
        pass  # La tarea fue cancelada, probablemente porque se reprodujo una nueva canción


# Función para verificar si hay usuarios en el canal de voz
async def check_voice_channel(voice_client):
    while voice_client.is_connected():
        try:
            # Verificar si hay miembros en el canal de voz (excluyendo al bot)
            members = voice_client.channel.members
            real_members = [m for m in members if not m.bot]
            
            # Si no hay miembros reales, desconectar después de 10 segundos
            if not real_members:
                print("No hay usuarios en el canal, esperando 10 segundos antes de desconectar...")
                await asyncio.sleep(10)  # Esperar 10 segundos
                
                # Verificar nuevamente si no hay miembros (por si alguien se unió)
                if voice_client.is_connected():  # Verificar que el cliente siga conectado
                    members = voice_client.channel.members
                    real_members = [m for m in members if not m.bot]
                    
                    if not real_members and voice_client.is_connected():
                        print("Desconectando por inactividad (canal vacío)")
                        await voice_client.disconnect()
                        break
            
            # Verificar cada 5 segundos
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error en check_voice_channel: {e}")
            await asyncio.sleep(5)  # En caso de error, esperar y continuar
    return


@bot.tree.command(name="sync", description="Sincroniza los comandos con Discord")
async def sync(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
        await bot.tree.sync()
        await interaction.response.send_message("¡Comandos sincronizados con éxito!")
    else:
        await interaction.response.send_message("Necesitas permisos de administrador para usar este comando.")


@bot.tree.command(name="loop", description="Controla el modo de bucle (none, song, queue)")
async def loop(interaction: discord.Interaction, mode: str = None):
    guild_id = str(interaction.guild_id)
    
    # Si no se proporciona un modo, mostrar el modo actual
    if mode is None:
        current_mode = LOOP_MODES.get(guild_id, "none")
        await interaction.response.send_message(f"Modo de bucle actual: **{current_mode}**")
        return
    
    # Convertir a minúsculas para facilitar la comparación
    mode = mode.lower()
    
    # Verificar que el modo sea válido
    if mode not in ["none", "song", "queue"]:
        await interaction.response.send_message("Modo no válido. Opciones disponibles: none, song, queue")
        return
    
    # Establecer el modo de bucle
    LOOP_MODES[guild_id] = mode
    
    # Responder al usuario
    if mode == "none":
        await interaction.response.send_message("Modo de bucle desactivado.")
    elif mode == "song":
        await interaction.response.send_message("Modo de bucle activado: Repetir canción actual.")
    elif mode == "queue":
        await interaction.response.send_message("Modo de bucle activado: Repetir toda la cola.")


@bot.tree.command(name="clear", description="Limpia la cola de reproducción actual.")
async def clear(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    
    if guild_id not in SONG_QUEUES or not SONG_QUEUES[guild_id]:
        await interaction.response.send_message("La cola de reproducción ya está vacía.")
        return
    
    # Guardar la cantidad de canciones que había en la cola
    queue_size = len(SONG_QUEUES[guild_id])
    
    # Limpiar la cola
    SONG_QUEUES[guild_id].clear()
    
    await interaction.response.send_message(f"Se han eliminado {queue_size} canciones de la cola de reproducción.")


@bot.tree.command(name="shuffle", description="Mezcla aleatoriamente las canciones en la cola.")
async def shuffle(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    
    if guild_id not in SONG_QUEUES or not SONG_QUEUES[guild_id]:
        await interaction.response.send_message("La cola de reproducción está vacía.")
        return
    
    if len(SONG_QUEUES[guild_id]) < 2:
        await interaction.response.send_message("Necesitas al menos 2 canciones en la cola para mezclarlas.")
        return
    
    # Guardar la primera canción (la que se está reproduciendo actualmente)
    current_song = None
    if SONG_QUEUES[guild_id]:
        current_song = SONG_QUEUES[guild_id][0]
        remaining_songs = SONG_QUEUES[guild_id][1:]
        
        # Mezclar el resto de canciones
        import random
        random.shuffle(remaining_songs)
        
        # Reconstruir la cola con la canción actual al principio
        SONG_QUEUES[guild_id] = [current_song] + remaining_songs
    
    await interaction.response.send_message("La cola de reproducción ha sido mezclada aleatoriamente.")


@bot.tree.command(name="recommendations", description="Activa o desactiva las recomendaciones automáticas")
async def recommendations(interaction: discord.Interaction, enabled: bool = None):
    guild_id = str(interaction.guild_id)
    
    # Si no se proporciona un valor, mostrar el estado actual
    if enabled is None:
        current_state = RECOMMENDATIONS_ENABLED.get(guild_id, False)
        await interaction.response.send_message(f"Las recomendaciones automáticas están {'activadas' if current_state else 'desactivadas'}.")
        return
    
    # Establecer el nuevo estado
    RECOMMENDATIONS_ENABLED[guild_id] = enabled
    
    # Responder al usuario
    if enabled:
        await interaction.response.send_message("Recomendaciones automáticas activadas. Cuando termine la cola, se añadirán canciones similares.")
    else:
        await interaction.response.send_message("Recomendaciones automáticas desactivadas.")


@bot.tree.command(name="queue", description="Muestra la cola de reproducción actual.")
async def queue(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    
    if guild_id not in SONG_QUEUES or not SONG_QUEUES[guild_id]:
        await interaction.response.send_message("La cola de reproducción está vacía.")
        return
    
    queue_list = list(SONG_QUEUES[guild_id])
    
    # Crear un mensaje con la lista de canciones en cola
    message = "**Cola de reproducción:**\n"
    for i, (_, title) in enumerate(queue_list, 1):
        message += f"{i}. {title}\n"
    
    await interaction.response.send_message(message)


# Run the bot
bot.run(TOKEN)