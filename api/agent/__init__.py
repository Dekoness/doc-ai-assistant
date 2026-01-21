import azure.functions as func
import requests
import json
import os
import base64
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Agente RAG unificado que maneja:
    1. Chat de texto con conocimiento personalizado
    2. Imágenes + texto (OCR con Computer Vision)
    3. Historial de conversación
    4. Búsqueda en base de conocimiento
    """
    try:
        print("=== INICIO REQUEST ===")
        
        # Cargar variables de entorno
        VISION_KEY = os.environ.get("VISION_KEY")
        VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT")
        SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
        SEARCH_KEY = os.environ.get("SEARCH_ADMIN_KEY")
        SEARCH_INDEX = os.environ.get("SEARCH_INDEX_NAME", "knowledge-base-index")
        
        # Verificar variables esenciales
        if not all([VISION_KEY, VISION_ENDPOINT, OPENAI_KEY, OPENAI_ENDPOINT]):
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "Faltan variables de entorno esenciales"
                }),
                status_code=500,
                mimetype="application/json"
            )
        
        # Parsear request
        data = req.get_json()
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        print(f"Message: {message[:50] if message else 'empty'}")
        print(f"Has image: {bool(image_base64)}")
        
        # OCR si hay imagen
        ocr_text = None
        if image_base64:
            ocr_text = process_image_with_vision(image_base64, VISION_KEY, VISION_ENDPOINT)
            if ocr_text:
                message = f"[Imagen subida] Texto detectado:\n{ocr_text}\n\nUsuario dice: {message}"
            else:
                message = f"[Imagen subida sin texto detectado]\n\nUsuario dice: {message}"
        
        # 🔍 BÚSQUEDA EN BASE DE CONOCIMIENTO (si está configurado)
        context_from_kb = ""
        used_rag = False
        
        if SEARCH_ENDPOINT and SEARCH_KEY:
            print("🔍 Buscando en base de conocimiento...")
            context_from_kb = search_knowledge_base(
                query=message,
                search_endpoint=SEARCH_ENDPOINT,
                search_key=SEARCH_KEY,
                index_name=SEARCH_INDEX
            )
            
            if context_from_kb:
                used_rag = True
                print(f"✅ Contexto encontrado: {len(context_from_kb)} caracteres")
        
        # Llamar a OpenAI con contexto (KB + historial)
        gpt_response = call_openai_with_context(
            message=message,
            history=history,
            knowledge_base_context=context_from_kb,
            openai_key=OPENAI_KEY,
            openai_endpoint=OPENAI_ENDPOINT
        )
        
        # Construir respuesta
        response_data = {
            "success": True,
            "reply": gpt_response,
            "has_image": bool(image_base64),
            "extracted_text": ocr_text,
            "used_knowledge_base": used_rag,
            "history_updated": history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": gpt_response}
            ]
        }
        
        print("=== REQUEST EXITOSO ===")
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        print(f"ERROR GLOBAL: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )


def search_knowledge_base(query, search_endpoint, search_key, index_name):
    """
    🔍 Busca en Azure AI Search y devuelve contexto relevante
    
    Args:
        query: Pregunta del usuario
        search_endpoint: URL del servicio de búsqueda
        search_key: API Key de búsqueda
        index_name: Nombre del índice
    
    Returns:
        str: Contexto concatenado de los documentos encontrados
    """
    try:
        # Crear cliente de búsqueda
        credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential
        )
        
        # Realizar búsqueda semántica
        results = search_client.search(
            search_text=query,
            top=3,  # Top 3 resultados más relevantes
            select=["content", "metadata_storage_name"],  # Campos a recuperar
            include_total_count=True
        )
        
        # Construir contexto desde los resultados
        context_parts = []
        result_count = 0
        
        for result in results:
            result_count += 1
            
            # Extraer contenido
            content = result.get('content', '')
            source = result.get('metadata_storage_name', 'documento')
            
            # Limitar tamaño del fragmento (max 500 chars por doc)
            content_snippet = content[:500] if len(content) > 500 else content
            
            context_parts.append(
                f"[Fuente: {source}]\n{content_snippet}\n"
            )
        
        print(f"📚 Encontrados {result_count} documentos relevantes")
        
        if context_parts:
            return "\n---\n".join(context_parts)
        else:
            return ""
            
    except Exception as e:
        print(f"⚠️ Error en búsqueda (ignorando): {str(e)}")
        # No lanzar error, solo devolver vacío
        return ""


def process_image_with_vision(image_base64, vision_key, vision_endpoint):
    """Usa Azure Computer Vision para OCR"""
    try:
        print("Iniciando OCR...")
        
        if ',' in image_base64:
            image_data = base64.b64decode(image_base64.split(',')[1])
        else:
            image_data = base64.b64decode(image_base64)
        
        headers = {
            'Ocp-Apim-Subscription-Key': vision_key,
            'Content-Type': 'application/octet-stream'
        }
        
        url = f"{vision_endpoint.rstrip('/')}/vision/v3.2/read/analyze"
        
        print(f"Llamando a Vision API: {url}")
        response = requests.post(url, headers=headers, data=image_data, timeout=30)
        response.raise_for_status()
        
        operation_url = response.headers.get('Operation-Location')
        print(f"Operation URL: {operation_url}")
        
        for attempt in range(15):
            time.sleep(1)
            result = requests.get(
                operation_url, 
                headers={'Ocp-Apim-Subscription-Key': vision_key},
                timeout=10
            )
            result_json = result.json()
            
            status = result_json.get('status')
            print(f"Attempt {attempt + 1}: Status = {status}")
            
            if status == 'succeeded':
                lines = []
                for read_result in result_json.get('analyzeResult', {}).get('readResults', []):
                    for line in read_result.get('lines', []):
                        lines.append(line['text'])
                
                extracted_text = '\n'.join(lines)
                print(f"OCR completado: {len(lines)} líneas")
                return extracted_text
            
            elif status == 'failed':
                print("OCR falló")
                return None
        
        print("OCR timeout")
        return None
        
    except Exception as e:
        print(f"Error en OCR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def call_openai_with_context(message, history, knowledge_base_context, openai_key, openai_endpoint):
    """
    🤖 Llama a Azure OpenAI con contexto RAG
    
    Args:
        message: Mensaje del usuario
        history: Historial de conversación
        knowledge_base_context: Contexto recuperado de AI Search
        openai_key: API Key de OpenAI
        openai_endpoint: Endpoint de OpenAI
    
    Returns:
        str: Respuesta generada por GPT
    """
    try:
        print("Llamando a OpenAI...")
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': openai_key
        }
        
        # Construir URL completa
        if 'deployments' not in openai_endpoint:
            full_url = f"{openai_endpoint.rstrip('/')}/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2024-08-01-preview"
        else:
            full_url = openai_endpoint
        
        # 🎯 SYSTEM PROMPT con instrucciones RAG
        system_prompt = """Eres un asistente inteligente de Azure AI con acceso a una base de conocimiento.

INSTRUCCIONES IMPORTANTES:
1. Si recibes contexto de documentos [entre corchetes], úsalo como fuente principal de información
2. Cita la fuente cuando uses información de los documentos
3. Si no hay contexto relevante, responde con tu conocimiento general
4. Si no sabes algo, admítelo en lugar de inventar
5. Responde siempre en español de forma clara y concisa
6. Puedes analizar imágenes y extraer texto de ellas"""

        # Construir mensajes
        messages = [{"role": "system", "content": system_prompt}]
        
        # 📚 Agregar contexto de KB si existe
        if knowledge_base_context:
            kb_message = f"""📚 CONTEXTO DE LA BASE DE CONOCIMIENTO:

{knowledge_base_context}

---
Usa la información anterior para responder a la siguiente pregunta del usuario."""
            
            messages.append({"role": "system", "content": kb_message})
        
        # Agregar historial (últimos 10 mensajes)
        messages.extend(history[-10:])
        
        # Agregar mensaje actual
        messages.append({"role": "user", "content": message})
        
        payload = {
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.95
        }
        
        print(f"URL: {full_url}")
        print(f"Mensajes en contexto: {len(messages)}")
        
        response = requests.post(full_url, headers=headers, json=payload, timeout=60)
        
        print(f"Status code: {response.status_code}")
        
        response.raise_for_status()
        
        result = response.json()
        gpt_reply = result['choices'][0]['message']['content']
        
        print(f"GPT respondió: {gpt_reply[:100]}")
        return gpt_reply
        
    except Exception as e:
        print(f"Error en OpenAI: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error al procesar con GPT: {str(e)}"