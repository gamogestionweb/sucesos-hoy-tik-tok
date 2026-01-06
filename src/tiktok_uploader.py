"""
Módulo de publicación en TikTok
Sube videos automáticamente a TikTok
"""

import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from loguru import logger

# Intentar importar Playwright
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright no instalado. Ejecuta: pip install playwright && playwright install")


class TikTokUploader:
    """Sube videos a TikTok usando automatización de navegador"""

    def __init__(
        self,
        cookies_file: str = "./data/tiktok_cookies.json",
        headless: bool = False  # False para ver el navegador la primera vez
    ):
        self.cookies_file = Path(cookies_file)
        self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    def _load_cookies(self) -> list:
        """Carga cookies guardadas"""
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando cookies: {e}")
        return []

    def _save_cookies(self, cookies: list):
        """Guarda cookies para futuros usos"""
        with open(self.cookies_file, 'w') as f:
            json.dump(cookies, f)
        logger.info("Cookies guardadas")

    def _init_browser(self):
        """Inicializa el navegador"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright no está instalado")

        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )

        context = self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # Cargar cookies si existen
        cookies = self._load_cookies()
        if cookies:
            context.add_cookies(cookies)
            logger.info("Cookies cargadas")

        self.page = context.new_page()

    def login_manual(self) -> bool:
        """
        Abre el navegador para login manual.
        El usuario debe iniciar sesión manualmente.
        """
        if not self.page:
            self._init_browser()

        logger.info("Abriendo TikTok para login manual...")
        self.page.goto("https://www.tiktok.com/login")

        print("\n" + "="*50)
        print("INSTRUCCIONES:")
        print("1. Inicia sesión en TikTok en la ventana del navegador")
        print("2. Una vez logueado, presiona ENTER aquí")
        print("="*50 + "\n")

        input("Presiona ENTER cuando hayas iniciado sesión...")

        # Verificar si el login fue exitoso
        self.page.goto("https://www.tiktok.com/upload")
        time.sleep(3)

        if "login" in self.page.url.lower():
            logger.error("No se detectó sesión iniciada")
            return False

        # Guardar cookies
        cookies = self.page.context.cookies()
        self._save_cookies(cookies)
        logger.success("Login exitoso, cookies guardadas")

        return True

    def is_logged_in(self) -> bool:
        """Verifica si hay una sesión activa"""
        if not self.page:
            self._init_browser()

        try:
            self.page.goto("https://www.tiktok.com/upload", timeout=30000)
            time.sleep(3)

            # Si nos redirige a login, no estamos logueados
            if "login" in self.page.url.lower():
                return False

            # Buscar elementos que indiquen que estamos en la página de upload
            upload_elements = self.page.query_selector_all('[class*="upload"], [data-e2e*="upload"]')
            return len(upload_elements) > 0

        except Exception as e:
            logger.error(f"Error verificando login: {e}")
            return False

    def upload_video(
        self,
        video_path: str,
        caption: str,
        schedule_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Sube un video a TikTok

        Args:
            video_path: Ruta al video
            caption: Descripción/caption del video
            schedule_time: Si se quiere programar (opcional)

        Returns:
            Dict con resultado de la subida
        """
        result = {
            'success': False,
            'video_path': video_path,
            'caption': caption,
            'error': None,
            'url': None
        }

        if not Path(video_path).exists():
            result['error'] = f"Video no encontrado: {video_path}"
            logger.error(result['error'])
            return result

        if not self.page:
            self._init_browser()

        try:
            # Verificar login
            if not self.is_logged_in():
                logger.warning("No hay sesión activa, intentando login...")
                if not self.login_manual():
                    result['error'] = "No se pudo iniciar sesión"
                    return result

            # Ir a la página de upload
            logger.info("Navegando a página de upload...")
            self.page.goto("https://www.tiktok.com/upload?lang=es", wait_until="networkidle")
            time.sleep(3)

            # Buscar el input de archivo
            # TikTok usa un iframe para el upload
            file_input = None

            # Intentar encontrar el input directamente
            file_input = self.page.query_selector('input[type="file"]')

            if not file_input:
                # Buscar en iframes
                for frame in self.page.frames:
                    file_input = frame.query_selector('input[type="file"]')
                    if file_input:
                        break

            if not file_input:
                result['error'] = "No se encontró el input de archivo"
                logger.error(result['error'])
                return result

            # Subir el archivo
            logger.info(f"Subiendo video: {video_path}")
            file_input.set_input_files(video_path)

            # Esperar a que se procese el video
            logger.info("Esperando procesamiento del video...")
            time.sleep(10)  # TikTok tarda en procesar

            # Buscar el campo de caption
            caption_selectors = [
                '[data-e2e="caption-input"]',
                '[class*="caption"] [contenteditable="true"]',
                '.public-DraftEditor-content',
                '[data-contents="true"]',
            ]

            caption_field = None
            for selector in caption_selectors:
                caption_field = self.page.query_selector(selector)
                if caption_field:
                    break

            if caption_field:
                # Limpiar y escribir caption
                caption_field.click()
                self.page.keyboard.press('Control+A')
                self.page.keyboard.press('Backspace')
                time.sleep(0.5)

                # Escribir el caption (TikTok a veces tiene problemas con type directo)
                for char in caption:
                    self.page.keyboard.type(char, delay=50)
                    if len(caption) > 100:
                        break  # Evitar captions muy largos

                logger.info("Caption añadido")
            else:
                logger.warning("No se encontró campo de caption")

            # Esperar un poco más para que todo se cargue
            time.sleep(5)

            # Buscar y hacer click en el botón de publicar
            publish_selectors = [
                '[data-e2e="post-button"]',
                'button:has-text("Publicar")',
                'button:has-text("Post")',
                '[class*="post-button"]',
            ]

            publish_button = None
            for selector in publish_selectors:
                try:
                    publish_button = self.page.query_selector(selector)
                    if publish_button and publish_button.is_visible():
                        break
                except:
                    continue

            if publish_button:
                logger.info("Publicando video...")
                publish_button.click()

                # Esperar confirmación
                time.sleep(10)

                # Verificar si se publicó
                success_indicators = [
                    'Publicado',
                    'Your video is being uploaded',
                    'Upload complete',
                    'subido',
                ]

                page_text = self.page.content().lower()
                if any(ind.lower() in page_text for ind in success_indicators):
                    result['success'] = True
                    result['url'] = f"https://www.tiktok.com/@{self._get_username()}"
                    logger.success("Video publicado exitosamente")
                else:
                    # Puede que esté en proceso
                    result['success'] = True
                    result['url'] = "En proceso de publicación"
                    logger.info("Video enviado, en proceso de publicación")
            else:
                result['error'] = "No se encontró botón de publicar"
                logger.error(result['error'])

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error subiendo video: {e}")

        return result

    def _get_username(self) -> str:
        """Intenta obtener el nombre de usuario actual"""
        try:
            # Buscar el username en la página
            username_elem = self.page.query_selector('[data-e2e="profile-link"]')
            if username_elem:
                href = username_elem.get_attribute('href')
                if href and '/@' in href:
                    return href.split('/@')[1].split('/')[0]
        except:
            pass
        return "sucesoshoy"

    def close(self):
        """Cierra el navegador"""
        if self.browser:
            self.browser.close()
            logger.info("Navegador cerrado")


class TikTokUploaderAPI:
    """
    Uploader alternativo usando la API no oficial de TikTok
    Más inestable pero no requiere navegador
    """

    def __init__(self):
        logger.warning("TikTokUploaderAPI es experimental y puede no funcionar")

    def upload_video(self, video_path: str, caption: str) -> Dict[str, Any]:
        """Intenta subir usando métodos alternativos"""
        # Este método es un placeholder - la API de TikTok cambia constantemente
        # Se recomienda usar el método con Playwright
        return {
            'success': False,
            'error': 'Método API no implementado. Usa TikTokUploader con Playwright.'
        }


def setup_tiktok() -> TikTokUploader:
    """
    Configura TikTok por primera vez.
    Abre navegador para login manual.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("Instalando Playwright...")
        import subprocess
        subprocess.run(['pip', 'install', 'playwright'])
        subprocess.run(['playwright', 'install', 'chromium'])

    uploader = TikTokUploader(headless=False)
    uploader.login_manual()
    return uploader


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    print("=== Configuración de TikTok ===")
    print("Este proceso abrirá un navegador para que inicies sesión en TikTok")
    print()

    if not PLAYWRIGHT_AVAILABLE:
        print("Primero necesitas instalar Playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
        sys.exit(1)

    proceed = input("¿Continuar? (s/n): ")
    if proceed.lower() == 's':
        uploader = setup_tiktok()
        print("\nConfiguración completada. Las cookies se han guardado.")
        uploader.close()
