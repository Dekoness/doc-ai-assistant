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
    Optimizado para el índice 'certificado-federico'
    """
    try:
        credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential
        )
        
        print(f"🔎 Ejecutando búsqueda en '{index_name}': '{query[:50]}...'")
        
        # Búsqueda optimizada para tu índice
        results = search_client.search(
            search_text=query,
            top=3,
            include_total_count=True
        )
        
        context_parts = []
        result_count = 0
        
        for result in results:
            result_count += 1
            
            print(f"📄 Documento {result_count} encontrado")
            
            # 🎯 Extraer contenido del campo 'chunk'
            content = result.get('chunk', '')
            
            # 📋 Extraer metadatos útiles
            title = result.get('title', f'documento_{result_count}')
            key_phrases = result.get('keyPhrases', [])
            persons = result.get('persons', [])
            locations = result.get('locations', [])
            organizations = result.get('organizations', [])
            
            if content and len(content) > 20:
                # Construir contexto enriquecido
                enriched_content = f"📄 [Certificado: {title}]\n\n"
                
                # Agregar entidades extraídas si existen
                if persons:
                    enriched_content += f"👤 Personas: {', '.join(persons)}\n"
                if organizations:
                    enriched_content += f"🏢 Organizaciones: {', '.join(organizations)}\n"
                if locations:
                    enriched_content += f"📍 Ubicaciones: {', '.join(locations)}\n"
                if key_phrases:
                    enriched_content += f"🔑 Conceptos clave: {', '.join(key_phrases[:5])}\n"
                
                enriched_content += f"\n📝 Contenido:\n{content[:1200]}"
                
                context_parts.append(enriched_content)
                print(f"✅ Fragmento agregado: {title} ({len(content)} chars)")
            else:
                print(f"⚠️ Documento sin contenido suficiente")
        
        print(f"📊 Búsqueda completada: {result_count} resultados, {len(context_parts)} con contenido")
        
        if context_parts:
            return "\n\n" + "="*60 + "\n\n".join(context_parts)
        else:
            print("⚠️ No se encontró contexto útil")
            return ""
            
    except Exception as e:
        print(f"❌ Error en búsqueda: {str(e)}")
        import traceback
        traceback.print_exc()
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
    """🤖 Llama a Azure OpenAI con contexto RAG"""
    try:
        print("Llamando a OpenAI...")
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': openai_key
        }
        
        if 'deployments' not in openai_endpoint:
            full_url = f"{openai_endpoint.rstrip('/')}/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2024-08-01-preview"
        else:
            full_url = openai_endpoint
        
        # 🎯 SYSTEM PROMPT especializado en certificaciones
        system_prompt = """Eres un asistente especializado en información sobre Federico Zoppi y sus certificaciones profesionales.

INSTRUCCIONES:
1. Tienes acceso a certificados académicos y profesionales de Federico Zoppi
2. Cuando te presenten información de certificados, úsala como fuente AUTORITATIVA
3. Cita siempre el nombre del certificado cuando respondas
4. Si no encuentras información específica, di "No tengo esa información en los certificados disponibles"
5. Puedes mencionar: institución emisora, fecha, duración, conceptos clave
6. Responde en español de forma profesional y clara
7. Si te preguntan por certificados que no están en la base de datos, sé honesto

EJEMPLO DE RESPUESTA:
"Según el certificado de 4Geeks Academy, Federico Zoppi completó el programa Full Stack Software Developer de 360 horas en agosto de 2025."
"""

        messages = [{"role": "system", "content": system_prompt}]
        
        # 📚 Agregar contexto de certificados
        if knowledge_base_context:
            kb_message = f"""📚 CERTIFICADOS DE FEDERICO ZOPPI ENCONTRADOS:

{knowledge_base_context}

---
Usa ÚNICAMENTE esta información para responder. No inventes certificados que no aparecen aquí."""
            
            messages.append({"role": "system", "content": kb_message})
            print(f"📚 Contexto inyectado: {len(knowledge_base_context)} chars")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": message})
        
        payload = {
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.95
        }
        
        print(f"Mensajes en contexto: {len(messages)}")
        
        response = requests.post(full_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        gpt_reply = response.json()['choices'][0]['message']['content']
        print(f"GPT respondió: {gpt_reply[:100]}")
        
        return gpt_reply
        
    except Exception as e:
        print(f"Error en OpenAI: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error al procesar: {str(e)}"