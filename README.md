# Sucesos Hoy TikTok Bot

Bot automatizado para monitorear emergencias de Madrid y publicar en TikTok.

## Funcionalidades

- Monitorea la cuenta @EmergenciasMad en Twitter/X
- Descarga automaticamente los videos de los tweets
- Edita el video:
  - Corte aleatorio de segmentos
  - Conversion a formato vertical 9:16 (sin barras negras)
  - Texto superpuesto centrado con la noticia
  - Voz TTS en espanol narrando la noticia
- Reformula el texto automaticamente (misma noticia, diferentes palabras)
- Convierte @menciones a texto legible (ej: @BomberosMad -> Bomberos de Madrid)
- Elimina # de hashtags pero mantiene el contenido
- Publica automaticamente en TikTok

## Requisitos

- Python 3.10+
- FFmpeg instalado y en PATH
- Cuenta de Twitter Developer (API keys)
- Cuenta de TikTok

## Instalacion

1. Clonar el repositorio:
```bash
git clone https://github.com/gamogestionweb/sucesos-hoy-tik-tok.git
cd sucesos-hoy-tik-tok
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus API keys
```

4. Instalar FFmpeg:
   - Windows: Descargar de https://ffmpeg.org/download.html y agregar a PATH
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`

## Uso

### Ejecutar el bot (monitoreo continuo):
```bash
python bot.py
```

### Probar con un tweet especifico:
```bash
python test_tweet.py
```
Edita la variable TWEET_URL en el archivo para probar diferentes tweets.

## Estructura del Proyecto

```
sucesos-bot/
├── bot.py              # Bot principal con monitoreo continuo
├── test_tweet.py       # Script de prueba para tweets individuales
├── requirements.txt    # Dependencias Python
├── .env.example        # Plantilla de configuracion
├── .gitignore
└── src/
    ├── config.py           # Carga de configuracion
    ├── twitter_api.py      # Conexion API Twitter v2
    ├── twitter_monitor.py  # Monitoreo de cuenta
    ├── video_downloader.py # Descarga videos con yt-dlp
    ├── video_editor.py     # Edicion con FFmpeg
    ├── text_rewriter.py    # Reformulacion de texto
    ├── tts_generator.py    # Generacion de voz (edge-tts)
    └── tiktok_uploader.py  # Subida a TikTok (Playwright)
```

## Configuracion

| Variable | Descripcion |
|----------|-------------|
| TWITTER_USERNAME | Cuenta de Twitter a monitorear |
| TWITTER_BEARER_TOKEN | Token de API de Twitter |
| CHECK_INTERVAL | Intervalo de chequeo en segundos |
| MAX_CLIP_DURATION | Duracion maxima del clip (segundos) |
| MIN_CLIP_DURATION | Duracion minima del clip (segundos) |

## Licencia

MIT License

