#!/usr/bin/env python3
"""
Sucesos Bot - Bot automatizado para TikTok
Monitorea @EmergenciasMad y publica automáticamente en TikTok

Uso:
    python bot.py              # Ejecutar el bot
    python bot.py --setup      # Configurar TikTok (login)
    python bot.py --test       # Modo test (no publica)
    python bot.py --once       # Ejecutar una vez y salir
"""

import os
import sys
import time
import random
import argparse
from datetime import datetime
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger

from config import load_config, print_config
from twitter_monitor import TwitterMonitor
from video_downloader import VideoDownloader, check_ytdlp_installed

# Intentar importar el monitor con API oficial
try:
    from twitter_api import TwitterMonitorAPI
    TWITTER_API_AVAILABLE = True
except ImportError:
    TWITTER_API_AVAILABLE = False
from video_editor import VideoEditor, check_ffmpeg_installed
from text_rewriter import TextRewriter
from tiktok_uploader import TikTokUploader, PLAYWRIGHT_AVAILABLE


class SucesosBot:
    """Bot principal que coordina todo el proceso"""

    def __init__(self, test_mode: bool = False):
        self.config = load_config()
        self.test_mode = test_mode

        # Configurar logging
        self._setup_logging()

        # Inicializar componentes
        logger.info("Inicializando componentes...")

        # Usar API oficial si está configurada, sino scraping
        if self.config.twitter.has_api_credentials and TWITTER_API_AVAILABLE:
            logger.info("Usando API oficial de Twitter/X")
            self.monitor = TwitterMonitorAPI(
                username=self.config.twitter.username,
                bearer_token=self.config.twitter.bearer_token,
                data_dir=str(self.config.bot.data_dir)
            )
        else:
            logger.info("Usando scraping para Twitter/X (API no configurada)")
            self.monitor = TwitterMonitor(
                username=self.config.twitter.username,
                data_dir=str(self.config.bot.data_dir)
            )

        self.downloader = VideoDownloader(
            download_dir=str(self.config.bot.downloads_dir)
        )

        self.editor = VideoEditor(
            output_dir=str(self.config.bot.processed_dir),
            min_duration=self.config.video.min_duration,
            max_duration=self.config.video.max_duration
        )

        self.rewriter = TextRewriter(
            openai_api_key=self.config.bot.openai_api_key
        )

        if not test_mode:
            self.uploader = TikTokUploader(
                cookies_file=self.config.tiktok.cookies_file,
                headless=True  # Sin ventana en producción
            )
        else:
            self.uploader = None

        logger.success("Bot inicializado correctamente")

    def _setup_logging(self):
        """Configura el sistema de logging"""
        logger.remove()

        # Log a consola
        log_level = "DEBUG" if self.config.bot.debug else "INFO"
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        )

        # Log a archivo
        log_file = self.config.bot.logs_dir / "bot_{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_file),
            rotation="1 day",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
        )

    def process_tweet(self, tweet: dict) -> bool:
        """
        Procesa un tweet: descarga, edita, reformula y publica

        Args:
            tweet: Diccionario con info del tweet

        Returns:
            True si se procesó correctamente
        """
        tweet_id = tweet.get('id')
        tweet_url = tweet.get('url')
        tweet_text = tweet.get('text', '')

        logger.info(f"Procesando tweet: {tweet_id}")
        logger.debug(f"URL: {tweet_url}")
        logger.debug(f"Texto: {tweet_text[:100]}...")

        try:
            # 1. Descargar video
            logger.info("Paso 1/4: Descargando video...")
            download_result = self.downloader.download_twitter_video(
                tweet_url,
                output_name=f"tweet_{tweet_id}"
            )

            if not download_result:
                logger.error("Error descargando video")
                return False

            video_path = download_result['file_path']
            logger.success(f"Video descargado: {video_path}")

            # 2. Editar video
            logger.info("Paso 2/4: Editando video...")
            edit_result = self.editor.process_video(
                video_path,
                output_name=f"processed_{tweet_id}",
                force_vertical=self.config.video.force_vertical
            )

            if not edit_result:
                logger.error("Error editando video")
                return False

            processed_path = edit_result['processed_path']
            logger.success(f"Video editado: {processed_path}")
            logger.info(f"Segmento seleccionado: {edit_result['segment']['start']:.1f}s - {edit_result['segment']['end']:.1f}s")

            # 3. Reformular texto
            logger.info("Paso 3/4: Reformulando texto...")
            caption = self.rewriter.generate_caption(
                tweet_text,
                include_hashtags=True
            )
            logger.success(f"Caption generado: {caption[:80]}...")

            # 4. Publicar en TikTok
            if self.test_mode:
                logger.warning("MODO TEST: No se publicará en TikTok")
                logger.info(f"Video que se publicaría: {processed_path}")
                logger.info(f"Caption: {caption}")
            else:
                logger.info("Paso 4/4: Publicando en TikTok...")
                upload_result = self.uploader.upload_video(
                    processed_path,
                    caption
                )

                if upload_result['success']:
                    logger.success(f"Video publicado: {upload_result.get('url', 'OK')}")
                else:
                    logger.error(f"Error publicando: {upload_result.get('error')}")
                    return False

            # Marcar tweet como procesado
            self.monitor.mark_as_seen(tweet_id)
            logger.success(f"Tweet {tweet_id} procesado completamente")

            return True

        except Exception as e:
            logger.exception(f"Error procesando tweet {tweet_id}: {e}")
            return False

    def run_once(self) -> int:
        """
        Ejecuta una iteración del bot

        Returns:
            Número de tweets procesados
        """
        logger.info(f"Comprobando nuevos tweets de @{self.config.twitter.username}...")

        tweets = self.monitor.check_new_tweets()

        if not tweets:
            logger.info("No hay tweets nuevos con video")
            return 0

        logger.info(f"Encontrados {len(tweets)} tweets nuevos con video")

        processed = 0
        for tweet in tweets:
            if self.process_tweet(tweet):
                processed += 1
            else:
                # Si falla, no marcar como visto para reintentar
                logger.warning(f"Tweet {tweet.get('id')} fallido, se reintentará")

            # Pequeña pausa entre procesados
            time.sleep(5)

        return processed

    def run_forever(self):
        """Ejecuta el bot en bucle infinito con intervalos aleatorios"""
        logger.info("="*50)
        logger.info("Iniciando Sucesos Bot")
        logger.info(f"Monitoreando: @{self.config.twitter.username}")
        logger.info("Intervalo: 1-60 minutos (aleatorio)")
        logger.info("="*50)

        while True:
            try:
                self.run_once()

                # Intervalo aleatorio entre 1 y 60 minutos para evitar deteccion
                wait_minutes = random.uniform(1, 60)
                wait_seconds = int(wait_minutes * 60)
                logger.info(f"Proxima comprobacion en {wait_minutes:.1f} minutos...")
                time.sleep(wait_seconds)

            except KeyboardInterrupt:
                logger.info("Bot detenido por el usuario")
                break
            except Exception as e:
                logger.exception(f"Error en bucle principal: {e}")
                # Espera aleatoria tambien en caso de error
                wait_error = random.randint(30, 120)
                logger.info(f"Reintentando en {wait_error} segundos...")
                time.sleep(wait_error)

        # Limpieza
        if self.uploader:
            self.uploader.close()

        logger.info("Bot finalizado")


def check_dependencies() -> bool:
    """Verifica que todas las dependencias estén instaladas"""
    all_ok = True

    print("\n=== Verificando dependencias ===\n")

    # yt-dlp
    if check_ytdlp_installed():
        print("[OK] yt-dlp instalado")
    else:
        print("[X] yt-dlp NO instalado")
        print("    Instalar con: pip install yt-dlp")
        all_ok = False

    # ffmpeg
    if check_ffmpeg_installed():
        print("[OK] ffmpeg instalado")
    else:
        print("[X] ffmpeg NO instalado")
        print("    Descargar de: https://ffmpeg.org/download.html")
        all_ok = False

    # Playwright
    if PLAYWRIGHT_AVAILABLE:
        print("[OK] Playwright instalado")
    else:
        print("[X] Playwright NO instalado")
        print("    Instalar con: pip install playwright && playwright install chromium")
        all_ok = False

    print()
    return all_ok


def setup_tiktok():
    """Configura TikTok (login manual)"""
    print("\n=== Configuración de TikTok ===\n")

    if not PLAYWRIGHT_AVAILABLE:
        print("Primero instala Playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
        return

    config = load_config()
    uploader = TikTokUploader(
        cookies_file=config.tiktok.cookies_file,
        headless=False
    )

    success = uploader.login_manual()
    uploader.close()

    if success:
        print("\nConfiguración completada. Puedes ejecutar el bot.")
    else:
        print("\nError en la configuración. Inténtalo de nuevo.")


def main():
    parser = argparse.ArgumentParser(
        description="Sucesos Bot - Automatización de TikTok",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python bot.py              # Ejecutar el bot en bucle
  python bot.py --setup      # Configurar login de TikTok
  python bot.py --test       # Modo test (no publica)
  python bot.py --once       # Una iteración y salir
  python bot.py --config     # Ver configuración actual
        """
    )

    parser.add_argument('--setup', action='store_true',
                        help='Configurar TikTok (login manual)')
    parser.add_argument('--test', action='store_true',
                        help='Modo test (procesa pero no publica)')
    parser.add_argument('--once', action='store_true',
                        help='Ejecutar una vez y salir')
    parser.add_argument('--config', action='store_true',
                        help='Mostrar configuración actual')
    parser.add_argument('--check', action='store_true',
                        help='Verificar dependencias')

    args = parser.parse_args()

    # Verificar dependencias
    if args.check:
        check_dependencies()
        return

    # Mostrar configuración
    if args.config:
        config = load_config()
        print_config(config)
        return

    # Setup de TikTok
    if args.setup:
        setup_tiktok()
        return

    # Verificar dependencias básicas antes de iniciar
    if not check_dependencies():
        print("Instala las dependencias faltantes antes de continuar.")
        sys.exit(1)

    # Iniciar bot
    bot = SucesosBot(test_mode=args.test)

    if args.once:
        processed = bot.run_once()
        print(f"\nProcesados: {processed} tweets")
    else:
        bot.run_forever()


if __name__ == "__main__":
    main()
