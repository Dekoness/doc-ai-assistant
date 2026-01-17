from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()
app = Flask(__name__)

# Configuración
VISION_KEY = os.getenv("VISION_KEY")
VISION_ENDPOINT = os.getenv("VISION_ENDPOINT")
OPENAI_KEY = os.getenv("OPENAI_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")

# ======================
# RUTAS
# ======================
@app.route('/')
def home():
    return render_template('index.html')

# RUTA 1: ANALIZAR IMAGEN (Computer Vision OCR)
@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No se envió imagen"}), 400
        
        image_file = request.files['image']
        
        # Llamar a Azure Computer Vision OCR
        vision_url = f"{VISION_ENDPOINT}vision/v3.2/ocr"
        
        headers = {
            'Ocp-Apim-Subscription-Key': VISION_KEY,
            'Content-Type': 'application/octet-stream'
        }
        
        response = requests.post(vision_url, headers=headers, data=image_file.read())
        
        if response.status_code != 200:
            return jsonify({"error": f"Error Computer Vision: {response.text}"}), 500
        
        # Extraer texto
        result = response.json()
        extracted_text = ""
        
        if 'regions' in result:
            for region in result['regions']:
                for line in region['lines']:
                    for word in line['words']:
                        extracted_text += word['text'] + " "
                    extracted_text += "\n"
        
        return jsonify({
            "success": True,
            "extracted_text": extracted_text.strip(),
            "full_response": result
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# RUTA 2: CHAT CON GPT-4.1-mini (CORREGIDO)
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "No hay mensaje"}), 400
        
        # URL CORREGIDA - sin parámetro duplicado
        full_url = f"{OPENAI_ENDPOINT}"
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': OPENAI_KEY
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "Eres un asistente útil para un proyecto de portfolio de Azure AI. Responde en español."},
                {"role": "user", "content": message}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(full_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return jsonify({"error": f"Error OpenAI ({response.status_code}): {response.text}"}), 500
        
        result = response.json()
        reply = result['choices'][0]['message']['content']
        
        return jsonify({
            "success": True,
            "reply": reply,
            "tokens_used": result.get('usage', {})
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# RUTA 3: ANALIZAR TEXTO EXTRAÍDO CON GPT
@app.route('/analyze-extracted-text', methods=['POST'])
def analyze_extracted_text():
    """
    Toma texto extraído de OCR y lo analiza con GPT
    """
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({"error": "No hay texto para analizar"}), 400
        
        # Usar la misma función chat pero con prompt específico
        prompt = f"Analiza este texto extraído de una imagen mediante OCR y haz un resumen conciso:\n\n{text}"
        
        # Simulamos llamada a chat internamente
        full_url = f"{OPENAI_ENDPOINT}"
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': OPENAI_KEY
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "Eres un asistente especializado en análisis de documentos."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 300
        }
        
        response = requests.post(full_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            return jsonify({"error": f"Error OpenAI: {response.text}"}), 500
        
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        
        return jsonify({
            "success": True,
            "analysis": analysis,
            "original_text": text[:500] + "..." if len(text) > 500 else text
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Verificaciones
    print("=" * 50)
    print("🚀 PORTFOLIO AZURE AI - Backend")
    print("=" * 50)
    
    checks = {
        "Computer Vision": bool(VISION_KEY and VISION_ENDPOINT),
        "OpenAI GPT-4.1": bool(OPENAI_KEY and OPENAI_ENDPOINT)
    }
    
    for service, status in checks.items():
        print(f"{'✅' if status else '❌'} {service}")
    
    print("\n📡 Endpoints disponibles:")
    print(f"  • POST /analyze-image     - OCR de imágenes")
    print(f"  • POST /chat              - Chat con GPT-4.1-mini")
    print(f"  • POST /analyze-extracted-text - Analizar texto con GPT")
    print(f"\n🌐 Frontend: http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, port=5000)