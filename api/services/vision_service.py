"""
Servicio de OCR usando Azure Computer Vision.
Extrae texto de imagenes usando la API Read v3.2.
"""
import base64
import time
import requests
from typing import Optional

from ..config import settings
from ..utils import logger


class VisionService:
    """Servicio para procesamiento de imagenes con Azure Computer Vision"""
    
    def __init__(self):
        self.config = settings.vision
        self.api_version = "v3.2"
    
    @property
    def analyze_url(self) -> str:
        """URL del endpoint de analisis"""
        return f"{self.config.endpoint.rstrip('/')}/vision/{self.api_version}/read/analyze"
    
    def _get_headers(self) -> dict:
        """Headers para las peticiones a la API"""
        return {
            'Ocp-Apim-Subscription-Key': self.config.key,
            'Content-Type': 'application/octet-stream'
        }
    
    def _decode_image(self, image_base64: str) -> bytes:
        """Decodifica imagen de base64 a bytes"""
        if ',' in image_base64:
            # Formato data:image/...;base64,XXXXX
            return base64.b64decode(image_base64.split(',')[1])
        return base64.b64decode(image_base64)
    
    def _poll_result(self, operation_url: str, max_attempts: int = 15) -> Optional[dict]:
        """Espera y obtiene el resultado de la operacion asincrona"""
        headers = {'Ocp-Apim-Subscription-Key': self.config.key}
        
        for attempt in range(max_attempts):
            time.sleep(1)
            
            try:
                response = requests.get(operation_url, headers=headers, timeout=10)
                result = response.json()
                
                status = result.get('status')
                
                if status == 'succeeded':
                    return result
                elif status == 'failed':
                    logger.error(f"OCR fallo en intento {attempt + 1}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error polling OCR: {str(e)}")
        
        logger.warn(f"OCR timeout despues de {max_attempts} intentos")
        return None
    
    def _extract_text_from_result(self, result: dict) -> str:
        """Extrae el texto de los resultados del OCR"""
        lines = []
        
        for read_result in result.get('analyzeResult', {}).get('readResults', []):
            for line in read_result.get('lines', []):
                lines.append(line['text'])
        
        return '\n'.join(lines)
    
    def extract_text(self, image_base64: str) -> Optional[str]:
        """
        Extrae texto de una imagen usando OCR.
        
        Args:
            image_base64: Imagen codificada en base64
            
        Returns:
            Texto extraido o None si falla
        """
        if not self.config.is_configured:
            logger.error("Vision Service no configurado")
            return None
        
        try:
            logger.info("Procesando imagen con OCR...")
            
            # Decodificar imagen
            image_data = self._decode_image(image_base64)
            
            # Enviar a Azure
            response = requests.post(
                self.analyze_url,
                headers=self._get_headers(),
                data=image_data,
                timeout=30
            )
            response.raise_for_status()
            
            # Obtener URL de operacion
            operation_url = response.headers.get('Operation-Location')
            
            if not operation_url:
                logger.error("No se recibio Operation-Location")
                return None
            
            # Esperar resultado
            result = self._poll_result(operation_url)
            
            if not result:
                return None
            
            # Extraer texto
            text = self._extract_text_from_result(result)
            
            if text:
                logger.success(f"OCR exitoso: {len(text)} caracteres extraidos")
            else:
                logger.warn("OCR completado pero sin texto detectado")
            
            return text if text else None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red en OCR: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error en OCR: {str(e)}")
            return None


# Instancia singleton del servicio
vision_service = VisionService()
