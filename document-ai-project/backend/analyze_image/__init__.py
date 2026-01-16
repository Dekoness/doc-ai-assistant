import azure.functions as func
import json
import os

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="analyze_image")
def analyze_image(req: func.HttpRequest) -> func.HttpResponse:
    """Función simple de prueba conectada a Azure AI"""
    
    # 1. Verificar variables
    vision_endpoint = os.environ.get("VISION_ENDPOINT")
    vision_key = os.environ.get("VISION_KEY")
    
    if not vision_endpoint or not vision_key:
        return func.HttpResponse(
            json.dumps({"error": "Variables no configuradas"}),
            status_code=500
        )
    
    # 2. Por ahora, solo confirmar que funciona
    return func.HttpResponse(
        json.dumps({
            "status": "success",
            "message": "✅ Azure Function + Cognitive Services configurados",
            "vision_service": "ready" if vision_endpoint else "not_configured",
            "ocr_service": "ready" if os.environ.get("FORM_ENDPOINT") else "not_configured",
            "next_step": "Implementar Computer Vision API"
        }),
        mimetype="application/json"
    )