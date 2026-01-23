"""
Azure Function - Agente RAG
Handler principal que orquesta los servicios de Vision, Search y OpenAI.
"""
import json
import azure.functions as func

from ..config import settings
from ..utils import logger
from ..services import vision_service, search_service, openai_service


def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint principal del agente RAG.
    
    Recibe mensajes del usuario (opcionalmente con imagenes),
    busca contexto relevante en la base de conocimiento,
    y genera respuestas usando GPT.
    """
    try:
        logger.section("INICIO REQUEST")
        
        # Validar configuracion
        settings.print_status(logger)
        
        is_valid, missing = settings.validate_required()
        if not is_valid:
            logger.error(f"Faltan variables: {missing}")
            return _error_response("Faltan variables de entorno", 500)
        
        # Parsear request
        data = req.get_json()
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        logger.info(f"Mensaje: {message}")
        logger.info(f"Tiene imagen: {bool(image_base64)}")
        logger.info(f"Historial: {len(history)} mensajes")
        
        # Procesar imagen si existe
        ocr_text = None
        if image_base64:
            ocr_text = vision_service.extract_text(image_base64)
            if ocr_text:
                message = f"[Imagen adjunta]\n{ocr_text}\n\nPregunta: {message}"
        
        # Buscar en base de conocimiento (RAG)
        context_from_kb = ""
        used_rag = False
        
        if settings.search.is_configured:
            context_from_kb = search_service.search(message)
            used_rag = bool(context_from_kb)
            
            if used_rag:
                logger.success(f"RAG ACTIVADO - {len(context_from_kb)} chars de contexto")
            else:
                logger.warn("RAG NO ACTIVADO - Sin contexto recuperado")
        else:
            logger.warn("Search no configurado - RAG deshabilitado")
        
        # Llamar a GPT
        gpt_response = openai_service.chat(
            message=message,
            history=history,
            knowledge_context=context_from_kb
        )
        
        # Construir respuesta
        response_data = {
            "success": True,
            "reply": gpt_response,
            "has_image": bool(image_base64),
            "extracted_text": ocr_text,
            "used_knowledge_base": used_rag,
            "rag_limit_exceeded": settings.search.is_configured and not used_rag,
            "history_updated": history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": gpt_response}
            ]
        }
        
        logger.success("REQUEST COMPLETADO")
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
        
    except ValueError as e:
        logger.error(f"Error de validacion: {str(e)}")
        return _error_response(f"Datos invalidos: {str(e)}", 400)
        
    except Exception as e:
        logger.error(f"ERROR GLOBAL: {str(e)}")
        import traceback
        traceback.print_exc()
        return _error_response(str(e), 500)


def _error_response(message: str, status_code: int) -> func.HttpResponse:
    """Genera una respuesta de error estandarizada"""
    return func.HttpResponse(
        json.dumps({"success": False, "error": message}),
        status_code=status_code,
        mimetype="application/json"
    )
