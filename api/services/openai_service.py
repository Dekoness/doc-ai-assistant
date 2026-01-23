"""
Servicio de Azure OpenAI.
Maneja las llamadas a GPT con soporte para RAG.
"""
from typing import List, Dict, Optional
import requests

from ..config import settings
from ..utils import logger


class OpenAIService:
    """Servicio para interactuar con Azure OpenAI"""
    
    # Prompt del sistema base
    SYSTEM_PROMPT = """Eres un asistente de información profesional sobre Federico Zoppi.

REGLAS ESTRICTAS (NO NEGOCIABLES):
1. SOLO puedes mencionar información que aparezca EXPLÍCITAMENTE en los documentos proporcionados
2. NUNCA inventes, asumas o deduzcas certificaciones, títulos o experiencia
3. Si te preguntan por algo que NO está en los documentos: responde "No tengo esa información en los documentos disponibles"
4. NO uses tu conocimiento general del mundo - SOLO usa los documentos proporcionados
5. Cita siempre el nombre exacto del certificado/institución tal como aparece en los documentos

PROHIBIDO:
- Inventar certificaciones
- Mencionar PRINCE2, PMP, Scrum u otras certificaciones no presentes en los documentos
- Asumir experiencia laboral no documentada
- Usar información de tu entrenamiento previo

Responde en español de forma profesional pero honesta."""
    
    # Configuracion de la llamada
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TEMPERATURE = 0.3  # Baja para adherirse a hechos (era 0.7)
    DEFAULT_TIMEOUT = 60
    MAX_HISTORY_MESSAGES = 10
    
    def __init__(self):
        self.config = settings.openai
    
    def _get_headers(self) -> dict:
        """Headers para las peticiones a Azure OpenAI"""
        return {
            'Content-Type': 'application/json',
            'api-key': self.config.key
        }
    
    def _build_messages(
        self,
        user_message: str,
        history: List[Dict],
        knowledge_context: Optional[str] = None
    ) -> List[Dict]:
        """
        Construye el array de mensajes para la API.
        
        Args:
            user_message: Mensaje actual del usuario
            history: Historial de conversacion
            knowledge_context: Contexto de RAG (opcional)
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        
        # Agregar contexto RAG si existe
        if knowledge_context:
            kb_message = f"""INFORMACIÓN OFICIAL DE FEDERICO ZOPPI:

{knowledge_context}

---
IMPORTANTE: Esta es la ÚNICA información que puedes usar. NO menciones nada que no esté aquí explícitamente.
Si la respuesta no está en el texto de arriba, di que no tienes esa información."""
            messages.append({"role": "system", "content": kb_message})
            logger.success(f"Contexto RAG inyectado: {len(knowledge_context)} chars")
        else:
            # Sin contexto RAG - probablemente límite de consultas excedido
            logger.warn("Sin contexto RAG - límite de consultas posiblemente excedido")
            fallback_message = """IMPORTANTE: No tienes acceso a la base de conocimiento en este momento.

Cuando te pregunten sobre certificaciones, experiencia o información de Federico Zoppi, responde:

"Lo siento, he superado el límite diario de consultas a mi base de conocimiento (Azure AI Search tiene un límite de ~100 consultas/día en el plan gratuito). 

Puedes:
1. Intentar nuevamente en unas horas o mañana
2. Descargar mi CV directamente desde el botón de descarga
3. Preguntarme sobre otras funciones del asistente (OCR de imágenes, preguntas generales)

¡Gracias por tu comprensión!"

Para cualquier otra pregunta que no sea sobre información personal de Federico, puedes responder normalmente."""
            messages.append({"role": "system", "content": fallback_message})
        
        # Agregar historial (limitado)
        if history:
            messages.extend(history[-self.MAX_HISTORY_MESSAGES:])
        
        # Agregar mensaje actual
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def chat(
        self,
        message: str,
        history: List[Dict] = None,
        knowledge_context: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> str:
        """
        Envia un mensaje a GPT y obtiene respuesta.
        
        Args:
            message: Mensaje del usuario
            history: Historial de conversacion
            knowledge_context: Contexto de la base de conocimiento (RAG)
            max_tokens: Maximo de tokens en respuesta
            temperature: Temperatura de generacion
            
        Returns:
            Respuesta de GPT o mensaje de error
        """
        if not self.config.is_configured:
            return "Error: OpenAI no configurado"
        
        history = history or []
        max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        temperature = temperature or self.DEFAULT_TEMPERATURE
        
        try:
            logger.section("LLAMADA A GPT")
            logger.info(f"URL: {self.config.chat_url}")
            
            # Construir mensajes
            messages = self._build_messages(message, history, knowledge_context)
            logger.info(f"Total mensajes en contexto: {len(messages)}")
            
            # Payload
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Llamada a la API
            response = requests.post(
                self.config.chat_url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            
            # Extraer respuesta
            result = response.json()
            reply = result['choices'][0]['message']['content']
            
            logger.success(f"GPT respondio: {reply[:150]}...")
            
            return reply
            
        except requests.exceptions.Timeout:
            logger.error("Timeout en llamada a GPT")
            return "Error: La solicitud tomo demasiado tiempo"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red: {str(e)}")
            return f"Error de conexion: {str(e)}"
        except KeyError as e:
            logger.error(f"Respuesta inesperada de GPT: {str(e)}")
            return "Error: Respuesta inesperada del servicio"
        except Exception as e:
            logger.error(f"Error en GPT: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"


# Instancia singleton del servicio
openai_service = OpenAIService()
