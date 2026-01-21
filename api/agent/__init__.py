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
        print("=== INICIO REQUEST ===")
        
        VISION_KEY = os.environ.get("VISION_KEY")
        VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT")
        SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
        SEARCH_KEY = os.environ.get("SEARCH_ADMIN_KEY")
        SEARCH_INDEX = os.environ.get("SEARCH_INDEX_NAME", "certificado-federico")
        
        if not all([VISION_KEY, VISION_ENDPOINT, OPENAI_KEY, OPENAI_ENDPOINT]):
            return func.HttpResponse(
                json.dumps({"success": False, "error": "Faltan variables de entorno"}),
                status_code=500,
                mimetype="application/json"
            )
        
        data = req.get_json()
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        print(f"📝 Message: {message[:100]}")
        
        ocr_text = None
        if image_base64:
            ocr_text = process_image_with_vision(image_base64, VISION_KEY, VISION_ENDPOINT)
            if ocr_text:
                message = f"[Imagen adjunta]\n{ocr_text}\n\nPregunta: {message}"
        
        context_from_kb = ""
        used_rag = False
        
        if SEARCH_ENDPOINT and SEARCH_KEY:
            print(f"🔍 Buscando en índice: {SEARCH_INDEX}")
            context_from_kb = search_knowledge_base(
                query=message,
                search_endpoint=SEARCH_ENDPOINT,
                search_key=SEARCH_KEY,
                index_name=SEARCH_INDEX
            )
            
            if context_from_kb:
                used_rag = True
                print(f"✅ RAG activado: {len(context_from_kb)} chars")
        
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
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
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
        credential = AzureKeyCredential(search_key)
        search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=credential
        )
        
        print(f"🔎 Query: '{query[:100]}'")
        
        # Detectar consultas genéricas
        generic_keywords = ['qué certificados', 'cuáles certificados', 'todos', 'certificaciones', 
                           'titulos', 'formación', 'estudios', 'tiene federico']
        
        is_generic = any(kw in query.lower() for kw in generic_keywords)
        
        if is_generic:
            print("🌐 Consulta genérica - Obteniendo TODOS los certificados")
            results = search_client.search(search_text='*', top=10, include_total_count=True)
        else:
            print("🎯 Búsqueda específica")
            results = search_client.search(
                search_text=query,
                search_mode='any',
                search_fields=['chunk', 'title', 'keyPhrases', 'persons', 'organizations'],
                top=5,
                include_total_count=True
            )
        
        context_parts = []
        result_count = 0
        
        for result in results:
            result_count += 1
            
            content = result.get('chunk', '')
            title = result.get('title', f'doc_{result_count}')
            key_phrases = result.get('keyPhrases', [])
            persons = result.get('persons', [])
            organizations = result.get('organizations', [])
            locations = result.get('locations', [])
            
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
                print(f"✅ Agregado: {title}")
        
        print(f"📊 {result_count} resultados → {len(context_parts)} con contenido")
        
        return "\n\n" + "="*60 + "\n\n".join(context_parts) if context_parts else ""
            
    except Exception as e:
        print(f"❌ Error búsqueda: {str(e)}")
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
        headers = {'Content-Type': 'application/json', 'api-key': openai_key}
        
        if 'deployments' not in openai_endpoint:
            full_url = f"{openai_endpoint.rstrip('/')}/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2024-08-01-preview"
        else:
            full_url = openai_endpoint
        
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
            print(f"📚 Contexto: {len(knowledge_base_context)} chars")
        
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": message})
        
        response = requests.post(
            full_url, 
            headers=headers, 
            json={"messages": messages, "max_tokens": 1000, "temperature": 0.7},
            timeout=60
        )
        response.raise_for_status()
        
        return response.json()['choices'][0]['message']['content']
        
    except Exception as e:
        print(f"❌ GPT error: {str(e)}")
        return f"Error: {str(e)}"