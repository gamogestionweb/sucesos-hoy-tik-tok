"""
Módulo de monitoreo de Twitter/X
Monitorea una cuenta específica y detecta nuevos tweets con video
"""

import os
import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

import requests
from bs4 import BeautifulSoup
from loguru import logger

# Instancias de Nitter públicas (alternativa a la API de Twitter)
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.cz",
    "https://nitter.unixfox.eu",
]


class TwitterMonitor:
    """Monitorea una cuenta de Twitter/X para detectar nuevos tweets con video"""

    def __init__(self, username: str, data_dir: str = "./data"):
        self.username = username
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.seen_tweets_file = self.data_dir / "seen_tweets.json"
        self.seen_tweets = self._load_seen_tweets()
        self.working_instance = None

    def _load_seen_tweets(self) -> set:
        """Carga los IDs de tweets ya procesados"""
        if self.seen_tweets_file.exists():
            try:
                with open(self.seen_tweets_file, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.warning(f"Error cargando tweets vistos: {e}")
        return set()

    def _save_seen_tweets(self):
        """Guarda los IDs de tweets procesados"""
        with open(self.seen_tweets_file, 'w') as f:
            json.dump(list(self.seen_tweets), f)

    def mark_as_seen(self, tweet_id: str):
        """Marca un tweet como procesado"""
        self.seen_tweets.add(tweet_id)
        self._save_seen_tweets()

    def _find_working_instance(self) -> Optional[str]:
        """Encuentra una instancia de Nitter que funcione"""
        if self.working_instance:
            # Verificar si la instancia actual sigue funcionando
            try:
                response = requests.get(
                    f"{self.working_instance}/{self.username}",
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    return self.working_instance
            except:
                pass

        # Buscar una nueva instancia
        for instance in NITTER_INSTANCES:
            try:
                logger.info(f"Probando instancia: {instance}")
                response = requests.get(
                    f"{instance}/{self.username}",
                    timeout=10,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200 and "timeline" in response.text.lower():
                    self.working_instance = instance
                    logger.success(f"Instancia funcionando: {instance}")
                    return instance
            except Exception as e:
                logger.debug(f"Instancia {instance} falló: {e}")
                continue

        return None

    def _parse_nitter_page(self, html: str) -> List[Dict[str, Any]]:
        """Parsea la página de Nitter para extraer tweets"""
        soup = BeautifulSoup(html, 'html.parser')
        tweets = []

        # Buscar todos los tweets en el timeline
        timeline_items = soup.select('.timeline-item, .tweet-body')

        for item in timeline_items:
            try:
                tweet_data = {}

                # Obtener enlace del tweet (contiene el ID)
                tweet_link = item.select_one('.tweet-link, a[href*="/status/"]')
                if tweet_link:
                    href = tweet_link.get('href', '')
                    # Extraer ID del tweet de la URL
                    match = re.search(r'/status/(\d+)', href)
                    if match:
                        tweet_data['id'] = match.group(1)

                # Obtener texto del tweet
                tweet_content = item.select_one('.tweet-content, .content')
                if tweet_content:
                    tweet_data['text'] = tweet_content.get_text(strip=True)

                # Verificar si tiene video
                has_video = bool(item.select_one('.attachments video, .video-container, [class*="video"]'))
                tweet_data['has_video'] = has_video

                # Obtener URL del video si existe
                video_elem = item.select_one('video source, .attachments video')
                if video_elem:
                    tweet_data['video_url'] = video_elem.get('src', '')

                # Obtener fecha
                date_elem = item.select_one('.tweet-date a, time')
                if date_elem:
                    tweet_data['date'] = date_elem.get('title', date_elem.get_text(strip=True))

                # Solo añadir si tiene ID
                if tweet_data.get('id'):
                    tweet_data['url'] = f"https://twitter.com/{self.username}/status/{tweet_data['id']}"
                    tweets.append(tweet_data)

            except Exception as e:
                logger.debug(f"Error parseando tweet: {e}")
                continue

        return tweets

    def _fetch_via_syndication(self) -> List[Dict[str, Any]]:
        """Método alternativo usando syndication de Twitter"""
        try:
            # Twitter syndication API (público, sin autenticación)
            url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{self.username}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }

            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                # Parsear el HTML embebido
                soup = BeautifulSoup(response.text, 'html.parser')
                tweets = []

                # Buscar tweets en el timeline
                for article in soup.select('article, [data-tweet-id]'):
                    tweet_id = article.get('data-tweet-id')
                    if tweet_id:
                        tweets.append({
                            'id': tweet_id,
                            'url': f"https://twitter.com/{self.username}/status/{tweet_id}",
                            'text': article.get_text(strip=True)[:500],
                            'has_video': 'video' in str(article).lower()
                        })

                return tweets

        except Exception as e:
            logger.debug(f"Syndication falló: {e}")

        return []

    def check_new_tweets(self) -> List[Dict[str, Any]]:
        """
        Comprueba si hay nuevos tweets con video
        Retorna lista de tweets nuevos no procesados
        """
        new_tweets = []

        # Intentar con Nitter primero
        instance = self._find_working_instance()

        if instance:
            try:
                response = requests.get(
                    f"{instance}/{self.username}",
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )

                if response.status_code == 200:
                    tweets = self._parse_nitter_page(response.text)
                    logger.info(f"Encontrados {len(tweets)} tweets en Nitter")

                    for tweet in tweets:
                        if tweet.get('id') not in self.seen_tweets:
                            if tweet.get('has_video', False):
                                new_tweets.append(tweet)
                                logger.info(f"Nuevo tweet con video: {tweet.get('id')}")

                    return new_tweets

            except Exception as e:
                logger.error(f"Error con Nitter: {e}")

        # Fallback: usar syndication
        logger.info("Intentando método alternativo (syndication)...")
        tweets = self._fetch_via_syndication()

        for tweet in tweets:
            if tweet.get('id') not in self.seen_tweets:
                if tweet.get('has_video', False):
                    new_tweets.append(tweet)

        return new_tweets

    def get_tweet_url(self, tweet_id: str) -> str:
        """Construye la URL del tweet"""
        return f"https://twitter.com/{self.username}/status/{tweet_id}"


# Método alternativo usando yt-dlp para obtener info
def get_tweet_info_ytdlp(tweet_url: str) -> Optional[Dict[str, Any]]:
    """
    Usa yt-dlp para obtener información del tweet
    Más fiable que scraping pero más lento
    """
    import subprocess
    import json

    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-download', tweet_url],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            info = json.loads(result.stdout)
            return {
                'id': info.get('id'),
                'text': info.get('description', ''),
                'has_video': True,
                'url': tweet_url,
                'video_url': info.get('url'),
                'duration': info.get('duration'),
                'title': info.get('title')
            }
    except Exception as e:
        logger.error(f"Error con yt-dlp: {e}")

    return None


if __name__ == "__main__":
    # Test del módulo
    from loguru import logger
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    monitor = TwitterMonitor("EmergenciasMad")
    print("Buscando tweets nuevos...")

    tweets = monitor.check_new_tweets()
    print(f"\nEncontrados {len(tweets)} tweets nuevos con video:")

    for tweet in tweets:
        print(f"  - ID: {tweet.get('id')}")
        print(f"    URL: {tweet.get('url')}")
        print(f"    Texto: {tweet.get('text', '')[:100]}...")
        print()
