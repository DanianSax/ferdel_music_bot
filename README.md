# Ferdel Music Bot

Bot de música para Discord con sistema de cola y múltiples funcionalidades para reproducir música desde YouTube.

## Características

- **Reproducción de música**: Reproduce música desde YouTube mediante URLs o búsquedas de texto
- **Sistema de cola**: Gestiona una cola de reproducción para cada servidor
- **Controles de reproducción**: Pausa, reanuda, salta y detiene la reproducción
- **Soporte para listas de reproducción**: Añade automáticamente todas las canciones de una lista de reproducción de YouTube
- **Modo bucle**: Tres modos disponibles (sin bucle, repetir canción, repetir cola)
- **Reacciones interactivas**: Control mediante reacciones en los mensajes
- **Recomendaciones**: Sistema de recomendaciones basado en la canción actual
- **Modo aleatorio**: Mezcla aleatoriamente la cola de reproducción

## Comandos

- `/play [song_query]`: Reproduce una canción o la añade a la cola
- `/skip`: Salta la canción actual
- `/pause`: Pausa la reproducción
- `/resume`: Reanuda la reproducción
- `/stop`: Detiene la reproducción y limpia la cola
- `/queue`: Muestra la cola de reproducción actual

## Reacciones

- ⏯️: Pausa/Reanuda la reproducción
- ⏭️: Salta a la siguiente canción
- 🔁: Cambia el modo de bucle (ninguno → canción → cola → ninguno)
- 🔀: Mezcla aleatoriamente la cola
- ⏹️: Detiene la reproducción y desconecta el bot
- 📋: Muestra la cola de reproducción

## Dependencias

```
pip install discord.py
pip install python-dotenv
pip install yt-dlp
pip install PyNaCl
```

También necesitarás **FFmpeg** - Guarda los archivos ejecutables (.exe) en esta estructura de carpetas:
- *bin/ffmpeg/ffmpeg.exe*
- *bin/ffmpeg/ffplay.exe*
- *bin/ffmpeg/ffprobe.exe*

FFmpeg puede descargarse aquí: https://www.ffmpeg.org/download.html

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto con tu token de Discord:
   ```
   DISCORD_TOKEN=tu_token_aquí
   ```

2. Asegúrate de tener todas las dependencias instaladas
3. Ejecuta `python MusicBot.py` para iniciar el bot

## Notas

- El bot utiliza Git LFS para gestionar los archivos binarios de FFmpeg
- El archivo `.env` está excluido del repositorio por seguridad
