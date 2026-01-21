import azure.functions as func
import requests
import json
import os
import base64
import time
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Agente RAG unificado"""
    try:
        print("=" * 80)
        print("=== INICIO REQUEST ===")
        print("=" * 80)
        
        VISION_KEY = os.environ.get("VISION_KEY")
        VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT")
        SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
        SEARCH_KEY = os.environ.get("SEARCH_ADMIN_KEY")
        SEARCH_INDEX = os.environ.get("SEARCH_INDEX_NAME", "certificado-federico")
        
        print(f"🔑 Variables de entorno cargadas:")
        print(f"  VISION_KEY: {'✅ SET' if VISION_KEY else '❌ MISSING'}")
        print(f"  VISION_ENDPOINT: {VISION_ENDPOINT if VISION_ENDPOINT else '❌ MISSING'}")
        print(f"  OPENAI_KEY: {'✅ SET' if OPENAI_KEY else '❌ MISSING'}")
        print(f"  OPENAI_ENDPOINT: {OPENAI_ENDPOINT if OPENAI_ENDPOINT else '❌ MISSING'}")
        print(f"  SEARCH_ENDPOINT: {SEARCH_ENDPOINT if SEARCH_ENDPOINT else '❌ MISSING'}")
        print(f"  SEARCH_KEY: {'✅ SET' if SEARCH_KEY else '❌ MISSING'}")
        print(f"  SEARCH_INDEX: {SEARCH_INDEX}")
        
        if not all([VISION_KEY, VISION_ENDPOINT, OPENAI_KEY, OPENAI_ENDPOINT]):
            print("❌ Faltan variables de entorno esenciales")
            return func.HttpResponse(
                json.dumps({"success": False, "error": "Faltan variables de entorno"}),
                status_code=500,
                mimetype="application/json"
            )
        
        data = req.get_json()
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        print(f"\n📝 Mensaje del usuario: {message}")
        print(f"🖼️ Tiene imagen: {bool(image_base64)}")
        print(f"📚 Historial: {len(history)} mensajes")
        
        ocr_text = None
        if image_base64:
            print("\n🖼️ Procesando imagen con OCR...")
            ocr_text = process_image_with_vision(image_base64, VISION_KEY, VISION_ENDPOINT)
            if ocr_text:
                print(f"✅ OCR exitoso: {len(ocr_text)} caracteres")
                message = f"[Imagen adjunta]\n{ocr_text}\n\nPregunta: {message}"
            else:
                print("⚠️ OCR sin resultados")
        
        context_from_kb = ""
        used_rag = False
        
        print("\n" + "=" * 80)
        print("🔍 INICIANDO BÚSQUEDA EN BASE DE CONOCIMIENTO")
        print("=" * 80)
        
        if SEARCH_ENDPOINT and SEARCH_KEY:
            print(f"✅ Credenciales de búsqueda disponibles")
            print(f"   Endpoint: {SEARCH_ENDPOINT}")
            print(f"   Índice: {SEARCH_INDEX}")
            
            context_from_kb = search_knowledge_base(
                query=message,
                search_endpoint=SEARCH_ENDPOINT,
                search_key=SEARCH_KEY,
                index_name=SEARCH_INDEX
            )
            
            if context_from_kb:
                used_rag = True
                print(f"\n✅ RAG ACTIVADO - Contexto recuperado: {len(context_from_kb)} caracteres")
            else:
                print(f"\n⚠️ RAG NO ACTIVADO - No se recuperó contexto")
        else:
            print("❌ Credenciales de búsqueda NO disponibles")
            if not SEARCH_ENDPOINT:
                print("   Falta: SEARCH_ENDPOINT")
            if not SEARCH_KEY:
                print("   Falta: SEARCH_ADMIN_KEY")
        
        print("\n" + "=" * 80)
        print("🤖 LLAMANDO A GPT")
        print("=" * 80)
        
        gpt_response = call_openai_with_context(
            message=message,
            history=history,
            knowledge_base_context=context_from_kb,
            openai_key=OPENAI_KEY,
            openai_endpoint=OPENAI_ENDPOINT
        )
        
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
        
        print("\n✅ REQUEST COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        print(f"\n❌ ERROR GLOBAL: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return func.HttpResponse(
            json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


def search_knowledge_base(query, search_endpoint, search_key, index_name):
    """🔍 Búsqueda inteligente en certificados"""
    try:
        print(f"\n📍 Creando cliente de búsqueda...")
        print(f"   Endpoint: {search_endpoint}")
        print(f"   Index: {index_name}")
        
        credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential
        )
        
        print(f"✅ Cliente creado exitosamente")
        print(f"\n🔎 Query original: '{query[:200]}'")
        
        # Detectar consultas genéricas
        generic_keywords = ['qué certificados', 'cuáles certificados', 'todos', 'certificaciones', 
                           'titulos', 'formación', 'estudios', 'tiene federico', 'tiene zoppi']
        
        is_generic = any(kw in query.lower() for kw in generic_keywords)
        
        print(f"❓ ¿Es consulta genérica?: {is_generic}")
        
        if is_generic:
            print("🌐 Ejecutando búsqueda genérica (wildcard *) - Traerá TODOS los documentos")
            search_params = {
                'search_text': '*',
                'top': 10,
                'include_total_count': True
            }
        else:
            print("🎯 Ejecutando búsqueda específica")
            search_params = {
                'search_text': query,
                'search_mode': 'any',
                'search_fields': ['chunk', 'title', 'keyPhrases', 'persons', 'organizations'],
                'top': 5,
                'include_total_count': True
            }
        
        print(f"📋 Parámetros de búsqueda: {search_params}")
        
        results = search_client.search(**search_params)
        
        context_parts = []
        result_count = 0
        
        print(f"\n📊 Procesando resultados...")
        
        for result in results:
            result_count += 1
            
            print(f"\n--- DOCUMENTO {result_count} ---")
            print(f"   Keys: {list(result.keys())}")
            
            content = result.get('chunk', '')
            title = result.get('title', f'doc_{result_count}')
            key_phrases = result.get('keyPhrases', [])
            persons = result.get('persons', [])
            organizations = result.get('organizations', [])
            locations = result.get('locations', [])
            search_score = result.get('@search.score', 0)
            
            print(f"   📄 Título: {title}")
            print(f"   ⭐ Score: {search_score}")
            print(f"   📏 Longitud contenido: {len(content)} chars")
            print(f"   🏢 Organizaciones: {organizations}")
            print(f"   👤 Personas: {persons}")
            print(f"   📍 Ubicaciones: {locations}")
            print(f"   🔑 Key phrases: {key_phrases[:3]}")
            
            if content:
                print(f"   📝 Primeros 150 chars: {content[:150]}...")
            
            if content and len(content) > 20:
                enriched = f"📄 [{title}]\n\n"
                
                if persons:
                    enriched += f"👤 {', '.join(persons)}\n"
                if organizations:
                    enriched += f"🏢 {', '.join(organizations)}\n"
                if locations:
                    enriched += f"📍 {', '.join(locations)}\n"
                if key_phrases:
                    enriched += f"🔑 {', '.join(key_phrases[:7])}\n"
                
                enriched += f"\n{content[:1200]}"
                
                context_parts.append(enriched)
                print(f"   ✅ AGREGADO AL CONTEXTO")
            else:
                print(f"   ⚠️ DESCARTADO (contenido: {len(content)} chars)")
        
        print(f"\n📊 RESUMEN DE BÚSQUEDA:")
        print(f"   Total resultados procesados: {result_count}")
        print(f"   Documentos agregados al contexto: {len(context_parts)}")
        
        if context_parts:
            final_context = "\n\n" + "="*60 + "\n\n".join(context_parts)
            print(f"   ✅ Longitud contexto final: {len(final_context)} caracteres")
            return final_context
        else:
            print(f"   ❌ NO HAY CONTEXTO PARA DEVOLVER")
            return ""
            
    except Exception as e:
        print(f"\n❌ ERROR EN BÚSQUEDA: {str(e)}")
        import traceback
        traceback.print_exc()
        return ""


def process_image_with_vision(image_base64, vision_key, vision_endpoint):
    """OCR con Computer Vision"""
    try:
        if ',' in image_base64:
            image_data = base64.b64decode(image_base64.split(',')[1])
        else:
            image_data = base64.b64decode(image_base64)
        
        headers = {'Ocp-Apim-Subscription-Key': vision_key, 'Content-Type': 'application/octet-stream'}
        url = f"{vision_endpoint.rstrip('/')}/vision/v3.2/read/analyze"
        
        response = requests.post(url, headers=headers, data=image_data, timeout=30)
        response.raise_for_status()
        
        operation_url = response.headers.get('Operation-Location')
        
        for _ in range(15):
            time.sleep(1)
            result = requests.get(operation_url, headers={'Ocp-Apim-Subscription-Key': vision_key}, timeout=10)
            result_json = result.json()
            
            if result_json.get('status') == 'succeeded':
                lines = []
                for rr in result_json.get('analyzeResult', {}).get('readResults', []):
                    for line in rr.get('lines', []):
                        lines.append(line['text'])
                return '\n'.join(lines)
            elif result_json.get('status') == 'failed':
                return None
        
        return None
    except Exception as e:
        print(f"❌ OCR error: {str(e)}")
        return None


def call_openai_with_context(message, history, knowledge_base_context, openai_key, openai_endpoint):
    """🤖 GPT con RAG"""
    try:
        print(f"\n📡 Configurando llamada a OpenAI...")
        
        headers = {'Content-Type': 'application/json', 'api-key': openai_key}
        
        if 'deployments' not in openai_endpoint:
            full_url = f"{openai_endpoint.rstrip('/')}/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2024-08-01-preview"
        else:
            full_url = openai_endpoint
        
        print(f"   URL: {full_url}")
        
        system_prompt = """Eres un asistente especializado en Federico Zoppi y sus certificaciones.

INSTRUCCIONES:
1. Usa los certificados proporcionados como fuente AUTORITATIVA
2. Cita siempre el nombre del certificado/institución
3. Si no tienes información, di "No tengo esa información en los certificados"
4. Responde en español de forma profesional"""

        messages = [{"role": "system", "content": system_prompt}]
        
        if knowledge_base_context:
            kb_msg = f"""📚 CERTIFICADOS DE FEDERICO ZOPPI:

{knowledge_base_context}

---
Usa SOLO esta información."""
            messages.append({"role": "system", "content": kb_msg})
            print(f"✅ Contexto RAG inyectado: {len(knowledge_base_context)} caracteres")
        else:
            print(f"⚠️ NO hay contexto RAG - GPT usará conocimiento general")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": message})
        
        print(f"📨 Total mensajes en contexto: {len(messages)}")
        
        response = requests.post(
            full_url, 
            headers=headers, 
            json={"messages": messages, "max_tokens": 1000, "temperature": 0.7},
            timeout=60
        )
        response.raise_for_status()
        
        gpt_reply = response.json()['choices'][0]['message']['content']
        print(f"✅ GPT respondió: {gpt_reply[:150]}...")
        
        return gpt_reply
        
    except Exception as e:
        print(f"❌ Error en GPT: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}"