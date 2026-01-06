#!/usr/bin/env python3
"""
Script para probar con un tweet especifico
Con texto superpuesto y voz TTS
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger
from config import load_config
from video_downloader import VideoDownloader
from video_editor import VideoEditor
from text_rewriter import TextRewriter
from tiktok_uploader import TikTokUploader

# Configurar logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

# Tweet a procesar
TWEET_URL = "https://x.com/EmergenciasMad/status/2006966926791290942"
TWEET_ID = "2006966926791290942"


def generate_tts_audio(text: str, output_dir: Path) -> str:
    """Genera audio TTS para el texto"""
    try:
        from tts_generator import TTSGenerator
        tts = TTSGenerator(voice='elena', output_dir=str(output_dir))
        audio_path = tts.generate_audio(text, f"tts_{TWEET_ID}")
        return audio_path
    except ImportError:
        logger.warning("TTS no disponible. Instalando edge-tts...")
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'edge-tts'], capture_output=True)

        # Reintentar
        from tts_generator import TTSGenerator
        tts = TTSGenerator(voice='elena', output_dir=str(output_dir))
        return tts.generate_audio(text, f"tts_{TWEET_ID}")


def main():
    config = load_config()

    logger.info(f"Procesando tweet: {TWEET_URL}")

    # 1. Descargar video
    logger.info("\n=== DESCARGANDO VIDEO ===")
    downloader = VideoDownloader(download_dir=str(config.bot.downloads_dir))
    download_result = downloader.download_twitter_video(
        TWEET_URL,
        output_name=f"test_{TWEET_ID}"
    )

    if not download_result:
        logger.error("Error descargando video")
        return

    video_path = download_result['file_path']
    original_text = download_result.get('description', '') or download_result.get('title', '')

    logger.success(f"Video descargado: {video_path}")
    logger.info(f"Texto original: {original_text[:200] if original_text else 'No disponible'}...")

    # Si no hay texto, pedir al usuario
    if not original_text:
        print("\nNo se pudo extraer el texto del tweet.")
        original_text = input("Escribe el texto de la noticia: ")

    # Limpiar texto: @BomberosMad -> Bomberos de Madrid, #Carabanchel -> Carabanchel
    rewriter = TextRewriter(openai_api_key=config.bot.openai_api_key)
    cleaned_text = rewriter._clean_text(original_text)
    logger.info(f"Texto limpiado: {cleaned_text[:150]}...")

    # 2. Generar audio TTS
    logger.info("\n=== GENERANDO VOZ ===")
    audio_path = generate_tts_audio(cleaned_text, config.bot.processed_dir)

    if audio_path:
        logger.success(f"Audio generado: {audio_path}")
    else:
        logger.warning("No se pudo generar audio TTS")

    # 3. Editar video (corte aleatorio + texto + voz)
    logger.info("\n=== EDITANDO VIDEO ===")
    editor = VideoEditor(
        output_dir=str(config.bot.processed_dir),
        min_duration=config.video.min_duration,
        max_duration=config.video.max_duration
    )

    edit_result = editor.process_video(
        video_path,
        output_name=f"final_{TWEET_ID}",
        force_vertical=True,
        overlay_text=cleaned_text,  # Texto superpuesto (ya limpiado)
        tts_audio_path=audio_path   # Voz
    )

    if not edit_result:
        logger.error("Error editando video")
        return

    processed_path = edit_result['processed_path']
    logger.success(f"Video editado: {processed_path}")
    logger.info(f"Duracion original: {edit_result['original_duration']:.1f}s")
    logger.info(f"Segmento cortado: {edit_result['segment']['start']:.1f}s - {edit_result['segment']['end']:.1f}s")

    # 4. Generar caption para TikTok
    logger.info("\n=== GENERANDO CAPTION ===")
    caption = rewriter.generate_caption(original_text, include_hashtags=True)
    logger.success(f"Caption generado:")
    print(f"\n{caption}\n")

    # 5. Mostrar resultado
    print("\n" + "="*60)
    print("RESULTADO:")
    print("="*60)
    print(f"VIDEO: {processed_path}")
    print(f"DURACION: {edit_result['segment']['end'] - edit_result['segment']['start']:.1f}s")
    print(f"\nCAPTION:\n{caption}")
    print("="*60)

    # Abrir carpeta con el video
    import subprocess
    subprocess.run(['explorer', '/select,', processed_path], shell=True)

    # Preguntar si publicar
    respuesta = input("\n¿Publicar en TikTok? (s/n): ")

    if respuesta.lower() == 's':
        logger.info("\n=== PUBLICANDO EN TIKTOK ===")
        uploader = TikTokUploader(
            cookies_file=str(config.bot.data_dir / "tiktok_cookies.json"),
            headless=False
        )

        result = uploader.upload_video(processed_path, caption)

        if result['success']:
            logger.success("VIDEO PUBLICADO!")
        else:
            logger.error(f"Error: {result.get('error')}")

        uploader.close()
    else:
        logger.info("Publicacion cancelada")
        logger.info(f"El video editado esta en: {processed_path}")


if __name__ == "__main__":
    main()
