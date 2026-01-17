import azure.functions as func
import requests
import json
import os

app = func.FunctionApp()

@app.route(route="analyze-image", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def analyze_image(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Obtener imagen del request
        image_file = req.files.get('image')
        if not image_file:
            return func.HttpResponse(
                json.dumps({"error": "No se envió imagen"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Configuración desde variables de entorno
        vision_key = os.environ["VISION_KEY"]
        vision_endpoint = os.environ["VISION_ENDPOINT"]
        
        # Llamar a Azure Computer Vision
        vision_url = f"{vision_endpoint}vision/v3.2/ocr"
        
        headers = {
            'Ocp-Apim-Subscription-Key': vision_key,
            'Content-Type': 'application/octet-stream'
        }
        
        response = requests.post(vision_url, headers=headers, data=image_file.read())
        
        if response.status_code != 200:
            return func.HttpResponse(
                json.dumps({"error": f"Computer Vision error: {response.text}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Extraer texto
        result = response.json()
        extracted_text = ""
        
        if 'regions' in result:
            for region in result['regions']:
                for line in region['lines']:
                    for word in line['words']:
                        extracted_text += word['text'] + " "
                    extracted_text += "\n"
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "extracted_text": extracted_text.strip()
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )