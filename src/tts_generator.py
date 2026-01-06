"""
Modulo de Text-to-Speech (TTS)
Genera audio con voz sintetica para los videos
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

# Intentar importar edge-tts (gratuito, voces de Microsoft)
try:
    import edge_tts
    import asyncio
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


class TTSGenerator:
    """Genera audio con voz sintetica"""

    # Voces en espanol disponibles en edge-tts
    SPANISH_VOICES = {
        'elena': 'es-ES-ElviraNeural',      # Mujer espanola
        'alvaro': 'es-ES-AlvaroNeural',     # Hombre espanol
        'jorge': 'es-MX-JorgeNeural',       # Hombre mexicano
        'dalia': 'es-MX-DaliaNeural',       # Mujer mexicana
    }

    def __init__(self, voice: str = 'elena', output_dir: str = "./audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Seleccionar voz
        if voice in self.SPANISH_VOICES:
            self.voice = self.SPANISH_VOICES[voice]
        else:
            self.voice = voice  # Permitir voz personalizada

        logger.info(f"TTS configurado con voz: {self.voice}")

    def generate_audio(self, text: str, output_name: str = "tts_audio") -> Optional[str]:
        """
        Genera audio a partir de texto

        Args:
            text: Texto a convertir en voz
            output_name: Nombre del archivo de salida (sin extension)

        Returns:
            Ruta al archivo de audio generado o None si falla
        """
        if not EDGE_TTS_AVAILABLE:
            logger.warning("edge-tts no instalado. Instalar con: pip install edge-tts")
            return None

        output_path = self.output_dir / f"{output_name}.mp3"

        try:
            # Limpiar texto
            clean_text = self._clean_text(text)

            if not clean_text:
                logger.warning("Texto vacio, no se genera audio")
                return None

            logger.info(f"Generando audio para: {clean_text[:50]}...")

            # Generar audio usando edge-tts
            async def generate():
                communicate = edge_tts.Communicate(clean_text, self.voice)
                await communicate.save(str(output_path))

            asyncio.run(generate())

            if output_path.exists():
                logger.success(f"Audio generado: {output_path}")
                return str(output_path)
            else:
                logger.error("No se genero el archivo de audio")
                return None

        except Exception as e:
            logger.error(f"Error generando audio: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        """Limpia el texto para TTS"""
        import re

        # Eliminar URLs
        text = re.sub(r'https?://\S+', '', text)

        # Eliminar menciones
        text = re.sub(r'@\w+', '', text)

        # Eliminar hashtags
        text = re.sub(r'#\w+', '', text)

        # Eliminar emojis
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)

        # Limpiar espacios multiples
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def get_audio_duration(self, audio_path: str) -> float:
        """Obtiene la duracion del audio en segundos"""
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    audio_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Error obteniendo duracion: {e}")
            return 0


def check_tts_available() -> bool:
    """Verifica si TTS esta disponible"""
    if not EDGE_TTS_AVAILABLE:
        logger.warning("edge-tts no instalado")
        return False
    return True


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    if not check_tts_available():
        print("Instala edge-tts: pip install edge-tts")
        sys.exit(1)

    tts = TTSGenerator(voice='elena')
    audio = tts.generate_audio(
        "Bomberos del Ayuntamiento de Madrid trabajan en un incendio en la calle Alcala.",
        "test_audio"
    )

    if audio:
        print(f"Audio generado: {audio}")
