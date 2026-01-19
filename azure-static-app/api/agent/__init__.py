import azure.functions as func
import requests
import json
import os
import base64
from io import BytesIO

app = func.FunctionApp()

# Cargar variables de entorno
VISION_KEY = os.environ.get("VISION_KEY")
VISION_ENDPOINT = os.environ.get("VISION_ENDPOINT")
OPENAI_KEY = os.environ.get("OPENAI_KEY")
OPENAI_ENDPOINT = os.environ.get("OPENAI_ENDPOINT")

@app.route(route="agent", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def agent(req: func.HttpRequest) -> func.HttpResponse:
    """
    Agente unificado que maneja:
    1. Chat de texto
    2. Imágenes + texto (OCR con Computer Vision)
    3. Historial de conversación
    """
    try:
        data = req.get_json()
        
        message = data.get('message', '')
        image_base64 = data.get('image', None)
        history = data.get('history', [])
        
        # Si hay imagen, extraer texto con Computer Vision
        if image_base64:
            ocr_text = process_image_with_vision(image_base64)
            if ocr_text:
                message = f"[Imagen subida] Texto detectado: {ocr_text}\n\nUsuario dice: {message}"
            else:
                message = f"[Imagen subida sin texto detectado]\n\nUsuario dice: {message}"
        
        # Llamar a OpenAI con contexto
        gpt_response = call_openai_with_context(message, history)
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "reply": gpt_response,
                "has_image": bool(image_base64),
                "extracted_text": ocr_text if image_base64 else None,
                "history_updated": history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": gpt_response}
                ]
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

def process_image_with_vision(image_base64):
    """Usa Azure Computer Vision para OCR"""
    try:
        # Decodificar base64
        image_data = base64.b64decode(image_base64.split(',')[1] if ',' in image_base64 else image_base64)
        
        headers = {
            'Ocp-Apim-Subscription-Key': VISION_KEY,
            'Content-Type': 'application/octet-stream'
        }
        
        # Endpoint para OCR (Read API)
        url = f"{VISION_ENDPOINT}/vision/v3.2/read/analyze"
        
        response = requests.post(url, headers=headers, data=image_data)
        response.raise_for_status()
        
        # Obtener Operation-Location para polling
        operation_url = response.headers.get('Operation-Location')
        
        # Polling para obtener resultado
        import time
        for _ in range(10):
            time.sleep(1)
            result = requests.get(operation_url, headers={'Ocp-Apim-Subscription-Key': VISION_KEY})
            result_json = result.json()
            
            if result_json['status'] == 'succeeded':
                lines = []
                for read_result in result_json.get('analyzeResult', {}).get('readResults', []):
                    for line in read_result.get('lines', []):
                        lines.append(line['text'])
                return '\n'.join(lines)
        
        return None
        
    except Exception as e:
        print(f"Error en OCR: {str(e)}")
        return None

def call_openai_with_context(message, history):
    """Llama a Azure OpenAI con historial"""
    try:
        headers = {
            'Content-Type': 'application/json',
            'api-key': OPENAI_KEY
        }
        
        # Construir mensajes con historial
        messages = [
            {"role": "system", "content": "Eres un asistente útil que puede analizar texto de imágenes y responder preguntas."}
        ]
        messages.extend(history[-10:])  # Últimos 10 mensajes
        messages.append({"role": "user", "content": message})
        
        payload = {
            "messages": messages,
            "max_tokens": 800,
            "temperature": 0.7
        }
        
        response = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"Error al llamar a GPT: {str(e)}"