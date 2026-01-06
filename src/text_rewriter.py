"""
Módulo de reformulación de texto
Reescribe las noticias de emergencias con un estilo propio
"""

import os
import re
import random
from typing import Optional, List
from datetime import datetime

from loguru import logger

# Intentar importar OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class TextRewriter:
    """Reformula textos de noticias para TikTok"""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        self.client = None

        if self.openai_api_key and OPENAI_AVAILABLE:
            try:
                self.client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI configurado correctamente")
            except Exception as e:
                logger.warning(f"Error configurando OpenAI: {e}")

        # Plantillas para reformulación sin IA
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        """Carga plantillas de reformulación"""
        return {
            'intro': [
                "ATENCIÓN",
                "ÚLTIMA HORA",
                "URGENTE",
                "ALERTA",
                "SUCESO EN MADRID",
                "ESTO ACABA DE PASAR",
                "INCREÍBLE LO QUE HA PASADO",
            ],
            'incendio': [
                "Se ha producido un incendio {ubicacion}",
                "Bomberos trabajan en un incendio {ubicacion}",
                "Fuego declarado {ubicacion}",
                "Importante incendio {ubicacion}",
            ],
            'accidente': [
                "Accidente de tráfico {ubicacion}",
                "Colisión {ubicacion}",
                "Siniestro vial {ubicacion}",
                "Accidente con {detalles} {ubicacion}",
            ],
            'emergencia_sanitaria': [
                "Emergencia sanitaria {ubicacion}",
                "SAMUR atiende una emergencia {ubicacion}",
                "Intervención de emergencias {ubicacion}",
            ],
            'rescate': [
                "Rescate en marcha {ubicacion}",
                "Bomberos realizan un rescate {ubicacion}",
                "Operativo de rescate {ubicacion}",
            ],
            'generic': [
                "Suceso {ubicacion}",
                "Intervención de emergencias {ubicacion}",
                "Operativo en marcha {ubicacion}",
            ],
            'closing': [
                "Más información en breve.",
                "Os mantendremos informados.",
                "Pendientes de más detalles.",
                "",  # A veces sin cierre
            ]
        }

    def _detect_event_type(self, text: str) -> str:
        """Detecta el tipo de suceso basándose en palabras clave"""
        text_lower = text.lower()

        if any(word in text_lower for word in ['incendio', 'fuego', 'llamas', 'humo', 'arde']):
            return 'incendio'
        elif any(word in text_lower for word in ['accidente', 'colisión', 'choque', 'atropello', 'vuelco']):
            return 'accidente'
        elif any(word in text_lower for word in ['samur', 'sanitario', 'herido', 'atención médica']):
            return 'emergencia_sanitaria'
        elif any(word in text_lower for word in ['rescate', 'atrapado', 'salvamento']):
            return 'rescate'
        else:
            return 'generic'

    def _extract_location(self, text: str) -> str:
        """Extrae la ubicación del texto"""
        # Patrones comunes de ubicación
        patterns = [
            r'(?:en|calle|c/|avda\.?|avenida|plaza|pº|paseo)\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s,]+?)(?:\.|,|$|\d)',
            r'(?:distrito|barrio)\s+(?:de\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ\s]+)',
            r'([A-Za-záéíóúñÁÉÍÓÚÑ]+)\s*(?:nº|número|num\.?)\s*\d+',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) > 3:  # Evitar matches muy cortos
                    return f"en {location}"

        # Si no encontramos ubicación específica
        if 'madrid' in text.lower():
            return "en Madrid"

        return ""

    def _extract_details(self, text: str) -> str:
        """Extrae detalles adicionales del texto"""
        details = []

        # Buscar números de vehículos/personas afectadas
        num_match = re.search(r'(\d+)\s*(?:vehículos?|coches?|personas?|heridos?)', text, re.IGNORECASE)
        if num_match:
            details.append(num_match.group(0))

        # Buscar tipos de vehículos
        vehicles = re.findall(r'(?:moto|camión|autobús|furgoneta|turismo|coche)', text, re.IGNORECASE)
        if vehicles:
            details.extend(vehicles[:2])  # Máximo 2 vehículos

        return ' y '.join(details) if details else ""

    def rewrite_with_ai(self, original_text: str) -> Optional[str]:
        """Reformula el texto usando OpenAI"""
        if not self.client:
            return None

        try:
            prompt = f"""Eres el community manager de "Sucesos Hoy", una cuenta de TikTok que informa sobre emergencias en Madrid.

Reformula esta noticia de emergencias para TikTok:
"{original_text}"

Reglas:
1. Mantén la información esencial pero usa palabras diferentes
2. Estilo directo e impactante, pero sin sensacionalismo
3. Máximo 150 caracteres (es para descripción de TikTok)
4. NO uses emojis
5. NO copies frases textuales del original
6. Añade hashtags relevantes al final: #sucesoshoy #madrid #emergencias

Responde SOLO con el texto reformulado, nada más."""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.7
            )

            rewritten = response.choices[0].message.content.strip()
            logger.info(f"Texto reformulado con IA: {rewritten[:50]}...")
            return rewritten

        except Exception as e:
            logger.error(f"Error con OpenAI: {e}")
            return None

    def _extract_proper_names(self, text: str) -> dict:
        """Extrae nombres propios del texto (calles, lugares, entidades)"""
        proper_names = {
            'calles': [],
            'lugares': [],
            'entidades': [],
            'numeros': []
        }

        # Extraer calles
        calle_match = re.findall(r'(?:calle|c/|avda\.?|avenida|plaza|paseo|pº)\s+([A-Za-záéíóúñÁÉÍÓÚÑ\s]+?)(?:\s*(?:nº|número|,|\.|$))', text, re.IGNORECASE)
        proper_names['calles'] = [c.strip() for c in calle_match if len(c.strip()) > 2]

        # Extraer números de calle
        num_match = re.findall(r'(?:nº|número|num\.?)\s*(\d+)', text, re.IGNORECASE)
        proper_names['numeros'] = num_match

        # Extraer distritos/barrios
        distrito_match = re.findall(r'(?:distrito|barrio)\s+(?:de\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ\s]+)', text, re.IGNORECASE)
        proper_names['lugares'] = [d.strip() for d in distrito_match]

        # Extraer entidades conocidas
        entidades = ['Bomberos de Madrid', 'SAMUR', 'Protección Civil', 'Policía Municipal',
                     'Policía Nacional', 'Emergencias Madrid', 'SUMMA']
        for entidad in entidades:
            if entidad.lower() in text.lower():
                proper_names['entidades'].append(entidad)

        return proper_names

    def _reformulate_sentence(self, text: str, proper_names: dict) -> str:
        """Reformula una oración manteniendo nombres propios"""

        # Sinónimos para verbos comunes
        verb_synonyms = {
            'trabajan': ['intervienen', 'actúan', 'operan', 'están trabajando'],
            'atienden': ['asisten', 'auxilian', 'socorren', 'prestan ayuda'],
            'se ha producido': ['ha tenido lugar', 'se ha registrado', 'ha ocurrido'],
            'se desplazan': ['acuden', 'se dirigen', 'van camino'],
            'ha sido': ['fue', 'resultó', 'quedó'],
            'hay': ['se registran', 'se reportan', 'existen'],
        }

        # Sinónimos para sustantivos (mismo género gramatical)
        noun_synonyms = {
            'incendio': ['fuego', 'siniestro'],
            'accidente': ['siniestro vial', 'percance'],
            'heridos': ['lesionados', 'afectados'],
            'herido': ['lesionado', 'afectado'],
            'vehículos': ['coches', 'automóviles'],
            'vehículo': ['coche', 'automóvil'],
            'edificio': ['inmueble', 'bloque'],
            'vivienda': ['casa', 'vivienda'],  # mantener femenino
            'persona': ['ciudadano', 'persona'],
        }

        result = text

        # Reemplazar verbos
        for original, synonyms in verb_synonyms.items():
            if original in result.lower():
                replacement = random.choice(synonyms)
                result = re.sub(original, replacement, result, flags=re.IGNORECASE)

        # Reemplazar sustantivos (solo si no son nombres propios)
        for original, synonyms in noun_synonyms.items():
            if original in result.lower():
                # Verificar que no es parte de un nombre propio
                is_proper = False
                for names in proper_names.values():
                    for name in names:
                        if original.lower() in name.lower():
                            is_proper = True
                            break

                if not is_proper:
                    replacement = random.choice(synonyms)
                    result = re.sub(r'\b' + original + r'\b', replacement, result, flags=re.IGNORECASE)

        return result

    def rewrite_with_templates(self, original_text: str) -> str:
        """Reformula el texto manteniendo nombres propios pero cambiando palabras"""
        # Limpiar texto primero
        clean_text = self._clean_text(original_text)

        # Extraer nombres propios que debemos mantener
        proper_names = self._extract_proper_names(clean_text)

        event_type = self._detect_event_type(clean_text)
        location = self._extract_location(clean_text)
        details = self._extract_details(clean_text)

        # Construir el texto
        parts = []

        # Intro (variada)
        intro_options = [
            "ATENCIÓN",
            "ÚLTIMA HORA",
            "URGENTE",
            "ALERTA EN MADRID",
            "SUCESO AHORA",
            "ESTO ACABA DE PASAR",
            "NOTICIA DE ÚLTIMA HORA",
        ]
        if random.random() > 0.2:
            parts.append(random.choice(intro_options))

        # Reformular el texto original en vez de usar plantillas fijas
        reformulated = self._reformulate_sentence(clean_text, proper_names)

        # Si la reformulación es muy similar, usar plantilla
        if reformulated == clean_text or len(reformulated) < 20:
            template = random.choice(self.templates.get(event_type, self.templates['generic']))
            body = template.format(ubicacion=location, detalles=details)
        else:
            body = reformulated

        body = re.sub(r'\s+', ' ', body).strip()
        parts.append(body)

        # Cierre variado
        closing_options = [
            "Más información en breve.",
            "Os mantendremos informados.",
            "Seguimos pendientes.",
            "Ampliamos información.",
            "",
        ]
        closing = random.choice(closing_options)
        if closing:
            parts.append(closing)

        # Unir partes
        text = ' '.join(parts)

        # Añadir hashtags
        text += "\n\n#sucesoshoy #madrid #emergencias #ultimahora"

        return text

    def rewrite(self, original_text: str, prefer_ai: bool = True) -> str:
        """
        Reformula el texto de la noticia

        Args:
            original_text: Texto original del tweet
            prefer_ai: Si usar IA cuando esté disponible

        Returns:
            Texto reformulado para TikTok
        """
        if not original_text:
            return "#sucesoshoy #madrid #emergencias"

        # Limpiar el texto original
        original_text = self._clean_text(original_text)

        # Intentar con IA primero
        if prefer_ai and self.client:
            ai_result = self.rewrite_with_ai(original_text)
            if ai_result:
                return ai_result

        # Fallback a plantillas
        return self.rewrite_with_templates(original_text)

    def _clean_text(self, text: str) -> str:
        """
        Limpia y prepara el texto:
        - URLs eliminadas
        - @BomberosMad -> Bomberos de Madrid
        - Otras @ eliminadas
        - #hashtag -> hashtag (se mantiene el contenido)
        """
        # Eliminar URLs
        text = re.sub(r'https?://\S+', '', text)

        # Reemplazar menciones conocidas
        text = re.sub(r'@BomberosMad\b', 'Bomberos de Madrid', text, flags=re.IGNORECASE)
        text = re.sub(r'@ABORPRL\b', 'Bomberos de Madrid', text, flags=re.IGNORECASE)
        text = re.sub(r'@EmergenciasMad\b', 'Emergencias Madrid', text, flags=re.IGNORECASE)
        text = re.sub(r'@ABORPRL_MAD\b', 'Bomberos de Madrid', text, flags=re.IGNORECASE)
        text = re.sub(r'@SamurPC\b', 'SAMUR Proteccion Civil', text, flags=re.IGNORECASE)
        text = re.sub(r'@polaborprl\b', 'Policia Municipal', text, flags=re.IGNORECASE)

        # Eliminar otras menciones @ desconocidas
        text = re.sub(r'@\w+', '', text)

        # Convertir hashtags en palabras (quitar # pero mantener contenido)
        text = re.sub(r'#(\w+)', r'\1', text)

        # Eliminar emojis
        text = re.sub(r'[\U00010000-\U0010ffff]', '', text)

        # Limpiar espacios
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def generate_caption(
        self,
        original_text: str,
        include_hashtags: bool = True,
        max_length: int = 150
    ) -> str:
        """
        Genera el caption completo para TikTok

        Args:
            original_text: Texto original
            include_hashtags: Si incluir hashtags
            max_length: Longitud máxima del texto (sin hashtags)
        """
        rewritten = self.rewrite(original_text)

        # Separar texto y hashtags
        if '#' in rewritten:
            parts = rewritten.split('#', 1)
            main_text = parts[0].strip()
            hashtags = '#' + parts[1] if len(parts) > 1 else ''
        else:
            main_text = rewritten
            hashtags = "#sucesoshoy #madrid #emergencias"

        # Truncar si es necesario
        if len(main_text) > max_length:
            main_text = main_text[:max_length-3] + "..."

        if include_hashtags:
            return f"{main_text}\n\n{hashtags}"
        else:
            return main_text


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    rewriter = TextRewriter()

    # Tests
    test_texts = [
        "Bomberos del Ayuntamiento de Madrid trabajan en un incendio en un edificio de viviendas en la calle Alcalá 123. Varias dotaciones desplazadas.",
        "SAMUR-Protección Civil atiende a dos heridos tras accidente de tráfico en la A-2 a la altura de Canillejas.",
        "Rescate de una persona atrapada en ascensor en la Plaza Mayor. Bomberos ya en el lugar.",
    ]

    print("=== Test de reformulación ===\n")

    for text in test_texts:
        print(f"Original: {text}")
        print(f"Reformulado: {rewriter.rewrite(text, prefer_ai=False)}")
        print("-" * 50)
