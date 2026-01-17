import azure.functions as func
import requests
import json
import os

app = func.FunctionApp()

@app.route(route="chat", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Obtener mensaje del body
        req_body = req.get_json()
        message = req_body.get('message', '')
        
        if not message:
            return func.HttpResponse(
                json.dumps({"error": "No message provided"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Configuración
        openai_key = os.environ["OPENAI_KEY"]
        openai_endpoint = os.environ["OPENAI_ENDPOINT"]  # Ya incluye api-version
        
        headers = {
            'Content-Type': 'application/json',
            'api-key': openai_key
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "Eres un asistente útil para un proyecto de portfolio de Azure AI. Responde en español."},
                {"role": "user", "content": message}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(openai_endpoint, headers=headers, json=payload)
        
        if response.status_code != 200:
            return func.HttpResponse(
                json.dumps({"error": f"OpenAI error: {response.text}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        result = response.json()
        reply = result['choices'][0]['message']['content']
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "reply": reply,
                "tokens_used": result.get('usage', {})
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )