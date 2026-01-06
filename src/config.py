"""
Configuración central del bot
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


@dataclass
class TwitterConfig:
    """Configuración de Twitter/X"""
    username: str = "EmergenciasMad"
    # API de Twitter (opcional pero recomendado)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    access_token_secret: Optional[str] = None
    bearer_token: Optional[str] = None

    def __post_init__(self):
        self.username = os.getenv('TWITTER_USERNAME', self.username)
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

    @property
    def has_api_credentials(self) -> bool:
        """Verifica si hay credenciales de API configuradas"""
        return bool(self.bearer_token) or all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret
        ])


@dataclass
class TikTokConfig:
    """Configuración de TikTok"""
    session_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    cookies_file: str = "./data/tiktok_cookies.json"

    def __post_init__(self):
        self.session_id = os.getenv('TIKTOK_SESSION_ID')
        self.username = os.getenv('TIKTOK_USERNAME')
        self.password = os.getenv('TIKTOK_PASSWORD')


@dataclass
class VideoConfig:
    """Configuración de procesamiento de video"""
    min_duration: int = 15
    max_duration: int = 60
    force_vertical: bool = True
    target_width: int = 1080
    target_height: int = 1920

    def __post_init__(self):
        self.min_duration = int(os.getenv('MIN_CLIP_DURATION', self.min_duration))
        self.max_duration = int(os.getenv('MAX_CLIP_DURATION', self.max_duration))


@dataclass
class BotConfig:
    """Configuración general del bot"""
    # Intervalos
    check_interval: int = 60  # segundos entre comprobaciones

    # Directorios
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    downloads_dir: Path = field(default_factory=lambda: Path("./downloads"))
    processed_dir: Path = field(default_factory=lambda: Path("./processed"))
    logs_dir: Path = field(default_factory=lambda: Path("./logs"))
    data_dir: Path = field(default_factory=lambda: Path("./data"))

    # Hashtags por defecto
    default_hashtags: List[str] = field(default_factory=lambda: [
        "#sucesoshoy",
        "#madrid",
        "#emergencias",
        "#ultimahora",
        "#noticias"
    ])

    # OpenAI
    openai_api_key: Optional[str] = None

    # Modo debug
    debug: bool = False

    def __post_init__(self):
        self.check_interval = int(os.getenv('CHECK_INTERVAL', self.check_interval))

        # Configurar directorios
        if os.getenv('DOWNLOADS_DIR'):
            self.downloads_dir = Path(os.getenv('DOWNLOADS_DIR'))
        if os.getenv('PROCESSED_DIR'):
            self.processed_dir = Path(os.getenv('PROCESSED_DIR'))
        if os.getenv('LOGS_DIR'):
            self.logs_dir = Path(os.getenv('LOGS_DIR'))

        # Crear directorios
        for dir_path in [self.downloads_dir, self.processed_dir, self.logs_dir, self.data_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Hashtags
        if os.getenv('DEFAULT_HASHTAGS'):
            self.default_hashtags = os.getenv('DEFAULT_HASHTAGS').split()

        # OpenAI
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Debug
        self.debug = os.getenv('DEBUG', '').lower() in ('true', '1', 'yes')


@dataclass
class Config:
    """Configuración completa"""
    twitter: TwitterConfig = field(default_factory=TwitterConfig)
    tiktok: TikTokConfig = field(default_factory=TikTokConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    bot: BotConfig = field(default_factory=BotConfig)


def load_config() -> Config:
    """Carga y retorna la configuración"""
    return Config()


def print_config(config: Config):
    """Imprime la configuración actual (ocultando secretos)"""
    print("\n=== Configuración del Bot ===\n")

    print("Twitter/X:")
    print(f"  Usuario a monitorear: @{config.twitter.username}")
    print(f"  API configurada: {'Sí' if config.twitter.has_api_credentials else 'No (usando scraping)'}")

    print("\nTikTok:")
    print(f"  Cookies guardadas: {'Sí' if Path(config.tiktok.cookies_file).exists() else 'No'}")

    print("\nVideo:")
    print(f"  Duración mínima: {config.video.min_duration}s")
    print(f"  Duración máxima: {config.video.max_duration}s")
    print(f"  Formato vertical: {'Sí' if config.video.force_vertical else 'No'}")

    print("\nBot:")
    print(f"  Intervalo de comprobación: {config.bot.check_interval}s")
    print(f"  OpenAI configurado: {'Sí' if config.bot.openai_api_key else 'No'}")
    print(f"  Directorio de descargas: {config.bot.downloads_dir}")
    print(f"  Directorio de procesados: {config.bot.processed_dir}")

    print("\nHashtags por defecto:")
    print(f"  {' '.join(config.bot.default_hashtags)}")

    print()


if __name__ == "__main__":
    config = load_config()
    print_config(config)
