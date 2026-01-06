"""
Módulo de monitoreo de Twitter/X usando la API oficial
Requiere credenciales de desarrollador de Twitter/X
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

import requests
from loguru import logger


class TwitterAPI:
    """Cliente para la API v2 de Twitter/X"""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        data_dir: str = "./data"
    ):
        self.bearer_token = bearer_token or os.getenv('TWITTER_BEARER_TOKEN')
        self.api_key = api_key or os.getenv('TWITTER_API_KEY')
        self.api_secret = api_secret or os.getenv('TWITTER_API_SECRET')
        self.access_token = access_token or os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = access_token_secret or os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.seen_tweets_file = self.data_dir / "seen_tweets.json"
        self.seen_tweets = self._load_seen_tweets()

        # Cache de user_id
        self._user_id_cache = {}

        if not self.bearer_token:
            raise ValueError("Se requiere TWITTER_BEARER_TOKEN")

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

    def _get_headers(self) -> dict:
        """Genera headers para las peticiones"""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        method: str = "GET"
    ) -> Optional[dict]:
        """Realiza una petición a la API"""
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=30
                )
            else:
                response = requests.post(
                    url,
                    headers=self._get_headers(),
                    json=params,
                    timeout=30
                )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limit
                reset_time = int(response.headers.get('x-rate-limit-reset', time.time() + 60))
                wait_time = reset_time - int(time.time()) + 1
                logger.warning(f"Rate limit alcanzado. Esperando {wait_time}s...")
                time.sleep(wait_time)
                return self._make_request(endpoint, params, method)
            else:
                logger.error(f"Error API {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error en petición: {e}")
            return None

    def get_user_id(self, username: str) -> Optional[str]:
        """Obtiene el ID de un usuario por su username"""
        if username in self._user_id_cache:
            return self._user_id_cache[username]

        result = self._make_request(f"users/by/username/{username}")

        if result and 'data' in result:
            user_id = result['data']['id']
            self._user_id_cache[username] = user_id
            return user_id

        return None

    def get_user_tweets(
        self,
        username: str,
        max_results: int = 10,
        since_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Obtiene los tweets recientes de un usuario

        Args:
            username: Nombre de usuario (sin @)
            max_results: Máximo de tweets a obtener (5-100)
            since_minutes: Solo tweets de los últimos X minutos

        Returns:
            Lista de tweets con info de videos
        """
        user_id = self.get_user_id(username)
        if not user_id:
            logger.error(f"Usuario no encontrado: {username}")
            return []

        # Calcular fecha de inicio
        start_time = (datetime.utcnow() - timedelta(minutes=since_minutes)).strftime('%Y-%m-%dT%H:%M:%SZ')

        params = {
            'max_results': min(max(5, max_results), 100),
            'start_time': start_time,
            'tweet.fields': 'created_at,text,attachments,entities',
            'expansions': 'attachments.media_keys',
            'media.fields': 'type,url,preview_image_url,duration_ms,variants',
        }

        result = self._make_request(f"users/{user_id}/tweets", params)

        if not result:
            return []

        tweets = []
        data = result.get('data', [])
        includes = result.get('includes', {})
        media_map = {}

        # Construir mapa de media
        for media in includes.get('media', []):
            media_map[media['media_key']] = media

        for tweet_data in data:
            tweet_id = tweet_data['id']

            # Verificar si tiene video
            has_video = False
            video_url = None

            if 'attachments' in tweet_data:
                media_keys = tweet_data['attachments'].get('media_keys', [])
                for key in media_keys:
                    media = media_map.get(key, {})
                    if media.get('type') == 'video':
                        has_video = True
                        # Intentar obtener URL del video
                        variants = media.get('variants', [])
                        for variant in variants:
                            if variant.get('content_type') == 'video/mp4':
                                video_url = variant.get('url')
                                break

            if has_video:
                tweets.append({
                    'id': tweet_id,
                    'text': tweet_data.get('text', ''),
                    'created_at': tweet_data.get('created_at'),
                    'url': f"https://twitter.com/{username}/status/{tweet_id}",
                    'has_video': True,
                    'video_url': video_url,
                })

        logger.info(f"Encontrados {len(tweets)} tweets con video de @{username}")
        return tweets

    def check_new_tweets(self, username: str) -> List[Dict[str, Any]]:
        """
        Comprueba si hay tweets nuevos con video

        Args:
            username: Usuario a monitorear

        Returns:
            Lista de tweets nuevos (no vistos) con video
        """
        tweets = self.get_user_tweets(username, max_results=10, since_minutes=120)

        new_tweets = []
        for tweet in tweets:
            if tweet['id'] not in self.seen_tweets:
                new_tweets.append(tweet)
                logger.info(f"Nuevo tweet con video: {tweet['id']}")

        return new_tweets


class TwitterMonitorAPI:
    """
    Monitor de Twitter usando la API oficial.
    Compatible con la interfaz de TwitterMonitor (scraping)
    """

    def __init__(
        self,
        username: str = "EmergenciasMad",
        bearer_token: Optional[str] = None,
        data_dir: str = "./data"
    ):
        self.username = username
        self.api = TwitterAPI(
            bearer_token=bearer_token,
            data_dir=data_dir
        )

    def check_new_tweets(self) -> List[Dict[str, Any]]:
        """Comprueba si hay tweets nuevos con video"""
        return self.api.check_new_tweets(self.username)

    def mark_as_seen(self, tweet_id: str):
        """Marca un tweet como procesado"""
        self.api.mark_as_seen(tweet_id)

    def get_tweet_url(self, tweet_id: str) -> str:
        """Construye la URL del tweet"""
        return f"https://twitter.com/{self.username}/status/{tweet_id}"


def test_api_connection(bearer_token: str) -> bool:
    """Prueba la conexión con la API de Twitter"""
    try:
        api = TwitterAPI(bearer_token=bearer_token)
        user_id = api.get_user_id("EmergenciasMad")
        if user_id:
            logger.success(f"Conexión exitosa. User ID: {user_id}")
            return True
        else:
            logger.error("No se pudo obtener el user ID")
            return False
    except Exception as e:
        logger.error(f"Error de conexión: {e}")
        return False


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

    if not bearer_token:
        print("Configura TWITTER_BEARER_TOKEN en el archivo .env")
        print("Puedes obtenerlo en: https://developer.twitter.com/")
        sys.exit(1)

    print("Probando conexión con la API de Twitter...")
    if test_api_connection(bearer_token):
        print("\nObteniendo tweets recientes de @EmergenciasMad...")
        monitor = TwitterMonitorAPI("EmergenciasMad", bearer_token)
        tweets = monitor.check_new_tweets()

        print(f"\nEncontrados {len(tweets)} tweets con video:")
        for tweet in tweets:
            print(f"  - {tweet['id']}: {tweet['text'][:80]}...")
