"""
Módulo de descarga de videos
Descarga videos de Twitter/X usando yt-dlp
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from loguru import logger


def get_ytdlp_command() -> List[str]:
    """Devuelve el comando para ejecutar yt-dlp"""
    # Intentar como comando directo primero
    try:
        result = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            return ['yt-dlp']
    except:
        pass

    # Usar como modulo de Python
    return [sys.executable, '-m', 'yt_dlp']


class VideoDownloader:
    """Descarga videos de Twitter/X y otras plataformas"""

    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_twitter_video(
        self,
        tweet_url: str,
        output_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Descarga un video de Twitter/X

        Args:
            tweet_url: URL del tweet
            output_name: Nombre del archivo (sin extensión). Si no se da, usa timestamp

        Returns:
            Dict con info del video descargado o None si falla
        """
        if not output_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"video_{timestamp}"

        output_template = str(self.download_dir / f"{output_name}.%(ext)s")
        json_file = self.download_dir / f"{output_name}.info.json"

        try:
            # Primero obtener info del video
            logger.info(f"Obteniendo info del video: {tweet_url}")

            ytdlp_cmd = get_ytdlp_command()
            info_result = subprocess.run(
                ytdlp_cmd + [
                    '--dump-json',
                    '--no-download',
                    tweet_url
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            video_info = {}
            if info_result.returncode == 0:
                video_info = json.loads(info_result.stdout)
                logger.info(f"Duración del video: {video_info.get('duration', 'desconocida')}s")

            # Descargar el video
            logger.info(f"Descargando video...")

            download_result = subprocess.run(
                ytdlp_cmd + [
                    '--format', 'best[ext=mp4]/best',  # Preferir MP4
                    '--output', output_template,
                    '--write-info-json',  # Guardar metadata
                    '--no-playlist',
                    '--socket-timeout', '30',
                    '--retries', '3',
                    tweet_url
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos máximo
            )

            if download_result.returncode != 0:
                logger.error(f"Error descargando: {download_result.stderr}")
                return None

            # Buscar el archivo descargado
            downloaded_files = list(self.download_dir.glob(f"{output_name}.*"))
            video_file = None

            for f in downloaded_files:
                if f.suffix.lower() in ['.mp4', '.webm', '.mkv', '.mov']:
                    video_file = f
                    break

            if not video_file:
                logger.error("No se encontró el video descargado")
                return None

            # Cargar info guardada
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    video_info = json.load(f)

            result = {
                'file_path': str(video_file),
                'filename': video_file.name,
                'duration': video_info.get('duration'),
                'title': video_info.get('title', ''),
                'description': video_info.get('description', ''),
                'uploader': video_info.get('uploader', ''),
                'upload_date': video_info.get('upload_date', ''),
                'view_count': video_info.get('view_count'),
                'tweet_url': tweet_url,
                'width': video_info.get('width'),
                'height': video_info.get('height'),
            }

            logger.success(f"Video descargado: {video_file}")
            return result

        except subprocess.TimeoutExpired:
            logger.error("Timeout descargando el video")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return None

    def get_video_info(self, tweet_url: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del video sin descargarlo

        Args:
            tweet_url: URL del tweet

        Returns:
            Dict con info del video o None
        """
        try:
            ytdlp_cmd = get_ytdlp_command()
            result = subprocess.run(
                ytdlp_cmd + [
                    '--dump-json',
                    '--no-download',
                    tweet_url
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                info = json.loads(result.stdout)
                return {
                    'duration': info.get('duration'),
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'has_video': True,
                    'width': info.get('width'),
                    'height': info.get('height'),
                }

        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")

        return None

    def cleanup_old_downloads(self, max_age_hours: int = 24):
        """Elimina descargas antiguas para ahorrar espacio"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        for file in self.download_dir.iterdir():
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        file.unlink()
                        logger.info(f"Eliminado archivo antiguo: {file.name}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {file.name}: {e}")


def check_ytdlp_installed() -> bool:
    """Verifica si yt-dlp está instalado"""
    import sys

    # Intentar como comando directo
    try:
        result = subprocess.run(
            ['yt-dlp', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"yt-dlp versión: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"Error con yt-dlp directo: {e}")

    # Intentar como modulo de Python
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'yt_dlp', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info(f"yt-dlp versión (módulo): {result.stdout.strip()}")
            return True
    except Exception as e:
        logger.debug(f"Error con yt-dlp módulo: {e}")

    logger.error("yt-dlp no está instalado")
    return False


if __name__ == "__main__":
    # Test del módulo
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    if not check_ytdlp_installed():
        print("Por favor instala yt-dlp: pip install yt-dlp")
        sys.exit(1)

    # Test con un tweet de ejemplo (cambiar por uno real)
    downloader = VideoDownloader("./test_downloads")

    # Ejemplo de uso
    test_url = "https://twitter.com/EmergenciasMad/status/EXAMPLE"
    print(f"Para probar, usa: downloader.download_twitter_video('{test_url}')")
