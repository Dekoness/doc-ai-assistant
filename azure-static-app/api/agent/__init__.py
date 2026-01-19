import azure.functions as func
import requests
import json
import os
import base64

app = func.FunctionApp()

@app.route(route="agent", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def agent(req: func.HttpRequest) -> func.HttpResponse:
    """
    Agente unificado que maneja:
    1. Chat de texto
    2. Imágenes + texto
    3. Futuro: memoria, entrenamiento
    """
    try:
        data = req.get_json()
        
        # 1. Procesar mensaje
        message = data.get('message', '')
        image_base64 = data.get('image', None)  # Imagen en base64
        history = data.get('history', [])      # Historial conversación
        
        response_text = ""
        
        # 2. Si hay imagen, usar Computer Vision
        if image_base64:
            # Extraer texto de imagen
            ocr_text = process_image_with_vision(image_base64)
            message = f"User uploaded image. Text in image: {ocr_text}. User says: {message}"
        
        # 3. Llamar a OpenAI con contexto
        gpt_response = call_openai_with_context(message, history)
        
        # 4. Construir respuesta
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "reply": gpt_response,
                "has_image": bool(image_base64),
                "history_updated": history + [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": gpt_response}
                ]
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

def process_image_with_vision(image_base64):
    """Usa Computer Vision para OCR"""
    # Tu código actual de Computer Vision aquí
    return "Texto extraído de imagen"

def call_openai_with_context(message, history):
    """Llama a OpenAI con historial"""
    # Tu código actual de OpenAI aquí
    return "Respuesta de GPT"