import azure.functions as func
import requests
import json
import os
import base64
import time

app = func.FunctionApp()

@app.route(route="agent", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def agent(req: func.HttpRequest) -> func.HttpResponse:
    """
    Agente unificado que maneja:
    1. Chat de texto
    2. Imágenes + texto (OCR con Computer Vision)
    3. Historial de conversación
    """
    try:
        # Log inicio
        print("=== INICIO REQUEST ===")
        
        # Cargar variables de entorno
        VISION_KEY = os.environ.get("VISION_KEY")
        VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT")
        OPENAI_KEY = os.environ.get("OPENAI_KEY")
        OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT")
        
        # Verificar variables
        if not all([VISION_KEY, VISION_ENDPOINT, OPENAI_KEY, OPENAI_ENDPOINT]):
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "Faltan variables de entorno",
                    "debug": {
                        "has_vision_key": bool(VISION_KEY),
                        "has_vision_endpoint": bool(VISION_ENDPOINT),
                        "has_openai_key": bool(OPENAI_KEY),
                        "has_openai_endpoint": bool(OPENAI_ENDPOINT)
                    }
                }),
                status_code=500,
                mimetype="application/json"
            )
        
        # Parsear request
        data = req.get_json()
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        print(f"Message: {message[:50]}")
        print(f"Has image: {bool(image_base64)}")
        
        # Si hay imagen, extraer texto con Computer Vision
        ocr_text = None
        if image_base64:
            ocr_text = process_image_with_vision(image_base64, VISION_KEY, VISION_ENDPOINT)
            if ocr_text:
                message = f"[Imagen subida] Texto detectado:\n{ocr_text}\n\nUsuario dice: {message}"
            else:
                message = f"[Imagen subida sin texto detectado]\n\nUsuario dice: {message}"
        
        # Llamar a OpenAI con contexto
        gpt_response = call_openai_with_context(message, history, OPENAI_KEY, OPENAI_ENDPOINT)
        
        # Construir respuesta
        response_data = {
            "success": True,
            "reply": gpt_response,
            "has_image": bool(image_base64),
            "extracted_text": ocr_text,
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


def process_image_with_vision(image_base64, vision_key, vision_endpoint):
    """Usa Azure Computer Vision para OCR"""
    try:
        print("Iniciando OCR...")
        
        # Decodificar base64
        if ',' in image_base64:
            image_data = base64.b64decode(image_base64.split(',')[1])
        else:
            image_data = base64.b64decode(image_base64)
        
        headers = {
            'Ocp-Apim-Subscription-Key': vision_key,
            'Content-Type': 'application/octet-stream'
        }
        
        # Endpoint para OCR (Read API)
        url = f"{vision_endpoint.rstrip('/')}/vision/v3.2/read/analyze"
        
        print(f"Llamando a Vision API: {url}")
        response = requests.post(url, headers=headers, data=image_data, timeout=30)
        response.raise_for_status()
        
        # Obtener Operation-Location para polling
        operation_url = response.headers.get('Operation-Location')
        print(f"Operation URL: {operation_url}")
        
        # Polling para obtener resultado
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


def call_openai_with_context(message, history, openai_key, openai_endpoint):
    """Llama a Azure OpenAI con historial"""
    try:
        print("Llamando a OpenAI...")
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': openai_key
        }
        
        # Construir mensajes con historial
        messages = [
            {
                "role": "system", 
                "content": "Eres un asistente útil que puede analizar texto de imágenes y responder preguntas. Responde siempre en español."
            }
        ]
        
        # Añadir últimos 10 mensajes del historial
        messages.extend(history[-10:])
        
        # Añadir mensaje actual
        messages.append({"role": "user", "content": message})
        
        payload = {
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.7
        }
        
        print(f"Endpoint: {openai_endpoint}")
        response = requests.post(openai_endpoint, headers=headers, json=payload, timeout=60)
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