"""
Módulo de edición automática de video
Detecta y extrae los fragmentos más impactantes del video
"""

import os
import random
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

import numpy as np
from loguru import logger

try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("moviepy no instalado, funcionalidad limitada")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class VideoSegment:
    """Representa un segmento de video"""
    start: float
    end: float
    score: float  # Puntuación de "impacto"
    reason: str


class VideoEditor:
    """Editor automático de videos para TikTok"""

    def __init__(
        self,
        output_dir: str = "./processed",
        min_duration: int = 15,
        max_duration: int = 60,
        target_aspect_ratio: Tuple[int, int] = (9, 16)  # TikTok vertical
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_aspect_ratio = target_aspect_ratio

    def analyze_video_intensity(self, video_path: str) -> List[VideoSegment]:
        """
        Analiza el video para encontrar los momentos más intensos/impactantes

        Usa análisis de:
        - Cambios bruscos de escena
        - Movimiento
        - Cambios de audio (si hay)
        """
        segments = []

        if not CV2_AVAILABLE:
            logger.warning("OpenCV no disponible, usando análisis básico")
            return self._basic_segment_analysis(video_path)

        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            if duration == 0:
                logger.error("No se pudo determinar la duración del video")
                return []

            # Analizar cada segundo del video
            frame_scores = []
            prev_frame = None
            sample_rate = max(1, int(fps / 2))  # Analizar 2 frames por segundo

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % sample_rate == 0:
                    # Convertir a escala de grises para análisis
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                    score = 0

                    if prev_frame is not None:
                        # Detectar cambios entre frames (movimiento/cambio de escena)
                        diff = cv2.absdiff(prev_frame, gray)
                        score = np.mean(diff)

                        # Bonus por cambios muy bruscos (posible cambio de escena)
                        if score > 30:
                            score *= 1.5

                    frame_scores.append({
                        'frame': frame_idx,
                        'time': frame_idx / fps,
                        'score': score
                    })

                    prev_frame = gray

                frame_idx += 1

            cap.release()

            # Encontrar los picos de intensidad
            if frame_scores:
                scores = [f['score'] for f in frame_scores]
                avg_score = np.mean(scores)
                std_score = np.std(scores)

                # Segmentos con puntuación por encima de la media + 0.5 std
                threshold = avg_score + 0.5 * std_score

                # Agrupar frames consecutivos con alta puntuación
                current_segment_start = None
                current_segment_scores = []

                for fs in frame_scores:
                    if fs['score'] > threshold:
                        if current_segment_start is None:
                            current_segment_start = fs['time']
                        current_segment_scores.append(fs['score'])
                    else:
                        if current_segment_start is not None:
                            segment_end = fs['time']
                            if segment_end - current_segment_start >= 2:  # Mínimo 2 segundos
                                segments.append(VideoSegment(
                                    start=max(0, current_segment_start - 1),
                                    end=min(duration, segment_end + 1),
                                    score=np.mean(current_segment_scores),
                                    reason="high_motion"
                                ))
                        current_segment_start = None
                        current_segment_scores = []

            # Si no encontramos segmentos destacados, usar el inicio
            if not segments:
                segments = self._basic_segment_analysis(video_path)

            logger.info(f"Encontrados {len(segments)} segmentos impactantes")
            return segments

        except Exception as e:
            logger.error(f"Error analizando video: {e}")
            return self._basic_segment_analysis(video_path)

    def _basic_segment_analysis(self, video_path: str) -> List[VideoSegment]:
        """Análisis básico cuando no hay OpenCV disponible"""
        try:
            # Obtener duración con ffprobe
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            duration = float(result.stdout.strip()) if result.returncode == 0 else 60

            # Estrategia básica: usar el inicio del video
            # (los videos de emergencias suelen tener lo importante al principio)
            end_time = min(self.max_duration, duration)

            return [VideoSegment(
                start=0,
                end=end_time,
                score=1.0,
                reason="default_start"
            )]

        except Exception as e:
            logger.error(f"Error en análisis básico: {e}")
            return [VideoSegment(start=0, end=self.max_duration, score=1.0, reason="fallback")]

    def select_best_segment(
        self,
        segments: List[VideoSegment],
        video_duration: float
    ) -> VideoSegment:
        """Selecciona un segmento aleatorio para TikTok (evita patrones detectables)"""

        # Añadir variacion aleatoria para evitar deteccion
        random_offset = random.uniform(-3, 3)  # +/- 3 segundos
        random_duration_adjust = random.uniform(0.8, 1.2)  # 80-120% de duracion

        if not segments or video_duration <= self.min_duration:
            # Video corto: usar todo con pequeña variacion
            start = max(0, random.uniform(0, 2))
            end = min(video_duration, video_duration - random.uniform(0, 2))
            return VideoSegment(
                start=start,
                end=max(end, start + self.min_duration),
                score=1.0,
                reason="short_video_random"
            )

        # Elegir aleatoriamente entre los mejores segmentos (no siempre el #1)
        sorted_segments = sorted(segments, key=lambda x: x.score, reverse=True)
        top_segments = sorted_segments[:min(3, len(sorted_segments))]
        best = random.choice(top_segments)

        # Aplicar offset aleatorio al inicio
        new_start = max(0, best.start + random_offset)

        # Calcular duracion con variacion
        base_duration = best.end - best.start
        target_duration = base_duration * random_duration_adjust
        target_duration = max(self.min_duration, min(self.max_duration, target_duration))

        # Aplicar variacion adicional a la duracion (+/- 5 segundos)
        target_duration += random.uniform(-5, 5)
        target_duration = max(self.min_duration, min(self.max_duration, target_duration))

        new_end = min(video_duration, new_start + target_duration)

        # Si el segmento es muy corto, ajustar inicio
        if new_end - new_start < self.min_duration:
            new_start = max(0, new_end - self.min_duration)

        logger.info(f"Corte aleatorio: {new_start:.1f}s - {new_end:.1f}s (variacion aplicada)")

        return VideoSegment(
            start=new_start,
            end=new_end,
            score=best.score,
            reason=f"{best.reason}_randomized"
        )

    def extract_clip(
        self,
        video_path: str,
        segment: VideoSegment,
        output_name: Optional[str] = None,
        add_watermark: bool = False
    ) -> Optional[str]:
        """
        Extrae un clip del video

        Args:
            video_path: Ruta al video original
            segment: Segmento a extraer
            output_name: Nombre del archivo de salida
            add_watermark: Si añadir marca de agua "SUCESOS HOY"
        """
        if not output_name:
            output_name = f"clip_{Path(video_path).stem}"

        output_path = self.output_dir / f"{output_name}.mp4"

        try:
            if MOVIEPY_AVAILABLE and add_watermark:
                return self._extract_with_moviepy(video_path, segment, str(output_path))
            else:
                return self._extract_with_ffmpeg(video_path, segment, str(output_path))

        except Exception as e:
            logger.error(f"Error extrayendo clip: {e}")
            return None

    def _extract_with_ffmpeg(
        self,
        video_path: str,
        segment: VideoSegment,
        output_path: str
    ) -> Optional[str]:
        """Extrae clip usando ffmpeg (más rápido)"""

        duration = segment.end - segment.start

        try:
            # Comando ffmpeg para extraer y recodificar
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(segment.start),
                '-i', video_path,
                '-t', str(duration),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0 and Path(output_path).exists():
                logger.success(f"Clip extraído: {output_path}")
                return output_path
            else:
                logger.error(f"Error ffmpeg: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error con ffmpeg: {e}")
            return None

    def _extract_with_moviepy(
        self,
        video_path: str,
        segment: VideoSegment,
        output_path: str
    ) -> Optional[str]:
        """Extrae clip usando moviepy (permite efectos)"""

        try:
            clip = VideoFileClip(video_path)
            subclip = clip.subclip(segment.start, segment.end)

            # Escribir el video
            subclip.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                logger=None  # Silenciar logs
            )

            clip.close()
            subclip.close()

            if Path(output_path).exists():
                logger.success(f"Clip extraído con moviepy: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"Error con moviepy: {e}")

        return None

    def convert_to_vertical(
        self,
        video_path: str,
        output_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Convierte video a formato vertical (9:16) para TikTok
        Hace CROP (recorta) para llenar toda la pantalla SIN barras negras
        """
        if not output_name:
            output_name = f"vertical_{Path(video_path).stem}"

        output_path = self.output_dir / f"{output_name}.mp4"

        try:
            # Detectar dimensiones actuales
            probe_cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0',
                video_path
            ]

            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            width, height = map(int, result.stdout.strip().split(','))

            # Dimensiones objetivo 9:16
            target_width = 1080
            target_height = 1920
            target_ratio = target_width / target_height  # 0.5625

            current_ratio = width / height

            # Estrategia: escalar para llenar y luego recortar el exceso
            # Esto elimina las barras negras y hace zoom al contenido
            if current_ratio > target_ratio:
                # Video mas ancho que 9:16 -> escalar por altura y recortar lados
                scale_filter = f"scale=-1:{target_height}"
                crop_filter = f"crop={target_width}:{target_height}"
            else:
                # Video mas alto que 9:16 -> escalar por ancho y recortar arriba/abajo
                scale_filter = f"scale={target_width}:-1"
                crop_filter = f"crop={target_width}:{target_height}"

            filter_complex = f"{scale_filter},{crop_filter}"

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', filter_complex,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.success(f"Video convertido a vertical (sin barras): {output_path}")
                return str(output_path)
            else:
                logger.warning(f"Error en conversion: {result.stderr[:200]}")

        except Exception as e:
            logger.error(f"Error convirtiendo a vertical: {e}")

        return None

    def add_text_overlay(
        self,
        video_path: str,
        text: str,
        output_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Añade texto superpuesto al video estilo TikTok
        - Texto CENTRADO en pantalla (vertical y horizontal)
        - Lineas cortas de max 18 caracteres
        - Texto blanco con borde negro grueso para que se lea bien
        """
        if not output_name:
            output_name = f"text_{Path(video_path).stem}"

        output_path = self.output_dir / f"{output_name}.mp4"

        import re
        # Limpiar texto - quitar URLs y caracteres problematicos para ffmpeg
        # NOTA: NO quitar @ ni # aqui porque ya vienen procesados del text_rewriter
        # @BomberosMad ya es "Bomberos de Madrid", #Carabanchel ya es "Carabanchel"
        clean_text = text
        clean_text = re.sub(r'https?://\S+', '', clean_text)
        # Solo quitar caracteres que rompen ffmpeg
        clean_text = re.sub(r"['\";:\\]", '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # Dividir en lineas CORTAS (max 18 chars) para video vertical 9:16
        words = clean_text.split()
        lines = []
        current_line = ""

        for word in words:
            # Si palabra muy larga, cortarla
            if len(word) > 16:
                word = word[:16]

            if len(current_line + " " + word) <= 18:
                current_line = (current_line + " " + word).strip()
            else:
                if current_line:
                    lines.append(current_line.upper())  # MAYUSCULAS para impacto
                current_line = word

        if current_line:
            lines.append(current_line.upper())

        # Max 7 lineas
        lines = lines[:7]

        if not lines:
            logger.warning("No hay texto para superponer")
            return video_path

        logger.info(f"Texto en {len(lines)} lineas:")
        for line in lines:
            logger.info(f"  -> {line}")

        try:
            # Crear un filtro por cada linea de texto
            filter_parts = []

            # Centro vertical: 1920/2 = 960
            # Cada linea tiene ~55px de alto
            total_text_height = len(lines) * 55
            y_start = (1920 - total_text_height) // 2

            for i, line in enumerate(lines):
                y_pos = y_start + (i * 55)
                safe_line = line.replace("'", "").replace('"', '')

                # drawtext con texto centrado
                text_filter = (
                    f"drawtext=text='{safe_line}':"
                    f"fontsize=46:"
                    f"fontcolor=white:"
                    f"borderw=5:"
                    f"bordercolor=black:"
                    f"x=(w-text_w)/2:"
                    f"y={y_pos}"
                )
                filter_parts.append(text_filter)

            full_filter = ','.join(filter_parts)

            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', full_filter,
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'copy',
                str(output_path)
            ]

            logger.info("Renderizando video con texto...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and output_path.exists():
                logger.success(f"Texto añadido OK: {output_path}")
                return str(output_path)
            else:
                logger.error(f"Error ffmpeg: {result.stderr[:400]}")
                return video_path

        except Exception as e:
            logger.error(f"Error añadiendo texto: {e}")
            return video_path

    def add_audio_overlay(
        self,
        video_path: str,
        audio_path: str,
        output_name: Optional[str] = None,
        mix_with_original: bool = True,
        original_volume: float = 0.2
    ) -> Optional[str]:
        """
        Añade audio (voz TTS) al video

        Args:
            video_path: Ruta al video
            audio_path: Ruta al audio TTS
            output_name: Nombre de salida
            mix_with_original: Si mezclar con audio original o reemplazar
            original_volume: Volumen del audio original (0-1)
        """
        if not output_name:
            output_name = f"voiced_{Path(video_path).stem}"

        output_path = self.output_dir / f"{output_name}.mp4"

        try:
            if mix_with_original:
                # Mezclar audio original (bajo) con TTS (alto)
                filter_complex = (
                    f"[0:a]volume={original_volume}[a0];"
                    f"[1:a]volume=1.0[a1];"
                    f"[a0][a1]amix=inputs=2:duration=first[aout]"
                )
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-i', audio_path,
                    '-filter_complex', filter_complex,
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest',
                    str(output_path)
                ]
            else:
                # Reemplazar audio completamente
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-i', audio_path,
                    '-map', '0:v',
                    '-map', '1:a',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-shortest',
                    str(output_path)
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and output_path.exists():
                logger.success(f"Audio añadido al video: {output_path}")
                return str(output_path)
            else:
                logger.warning(f"Error añadiendo audio: {result.stderr[:200]}")
                return video_path

        except Exception as e:
            logger.error(f"Error añadiendo audio: {e}")
            return video_path

    def process_video(
        self,
        video_path: str,
        output_name: Optional[str] = None,
        force_vertical: bool = True,
        overlay_text: Optional[str] = None,
        tts_audio_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Proceso completo: analiza, extrae el mejor fragmento, convierte,
        añade texto y voz

        Args:
            video_path: Ruta al video original
            output_name: Nombre base para los archivos de salida
            force_vertical: Si convertir a formato vertical
            overlay_text: Texto a superponer en el video
            tts_audio_path: Ruta al audio TTS para añadir

        Returns:
            Dict con información del video procesado
        """
        logger.info(f"Procesando video: {video_path}")

        # Obtener duración
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            video_duration = float(result.stdout.strip())
        except:
            video_duration = 60

        # Analizar video
        segments = self.analyze_video_intensity(video_path)

        # Seleccionar mejor segmento
        best_segment = self.select_best_segment(segments, video_duration)
        logger.info(f"Mejor segmento: {best_segment.start:.1f}s - {best_segment.end:.1f}s (score: {best_segment.score:.2f})")

        # Extraer clip
        clip_path = self.extract_clip(video_path, best_segment, output_name)

        if not clip_path:
            return None

        # Convertir a vertical si es necesario
        final_path = clip_path
        if force_vertical:
            vertical_path = self.convert_to_vertical(clip_path)
            if vertical_path:
                final_path = vertical_path

        # Añadir audio TTS PRIMERO (antes del texto)
        if tts_audio_path:
            audio_path = self.add_audio_overlay(final_path, tts_audio_path)
            if audio_path:
                final_path = audio_path

        # Añadir texto superpuesto AL FINAL (para que no se pierda)
        if overlay_text:
            text_path = self.add_text_overlay(final_path, overlay_text)
            if text_path:
                final_path = text_path

        return {
            'original_path': video_path,
            'processed_path': final_path,
            'segment': {
                'start': best_segment.start,
                'end': best_segment.end,
                'duration': best_segment.end - best_segment.start,
                'score': best_segment.score,
                'reason': best_segment.reason
            },
            'original_duration': video_duration
        }


def check_ffmpeg_installed() -> bool:
    """Verifica si ffmpeg y ffprobe están instalados"""
    for tool in ['ffmpeg', 'ffprobe']:
        try:
            result = subprocess.run(
                [tool, '-version'],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"{tool} no está funcionando correctamente")
                return False
        except FileNotFoundError:
            logger.error(f"{tool} no está instalado")
            return False

    return True


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    if not check_ffmpeg_installed():
        print("Por favor instala ffmpeg: https://ffmpeg.org/download.html")
        sys.exit(1)

    print("VideoEditor listo para usar")
    print("Uso: editor = VideoEditor(); editor.process_video('video.mp4')")
