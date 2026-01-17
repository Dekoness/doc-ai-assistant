import azure.functions as func
import requests
import json
import os
import logging

app = func.FunctionApp()

@app.route(route="chat", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    try:
        logging.info("CHAT FUNCTION STARTED")
        
        # 1. Get message
        req_body = req.get_json()
        message = req_body.get('message', '')
        logging.info(f"Message received: {message[:50]}")
        
        if not message:
            return func.HttpResponse(
                json.dumps({"error": "No message"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # 2. Check environment variables
        openai_key = os.environ.get("OPENAI_KEY")
        openai_endpoint = os.environ.get("OPENAI_ENDPOINT")
        
        logging.info(f"OpenAI Key exists: {bool(openai_key)}")
        logging.info(f"OpenAI Endpoint: {openai_endpoint}")
        
        if not openai_key or not openai_endpoint:
            return func.HttpResponse(
                json.dumps({"error": "Missing environment variables"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # 3. Call OpenAI
        headers = {
            'Content-Type': 'application/json',
            'api-key': openai_key
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": "Test"},
                {"role": "user", "content": message}
            ],
            "max_tokens": 100
        }
        
        logging.info(f"Calling OpenAI: {openai_endpoint}")
        
        response = requests.post(openai_endpoint, headers=headers, json=payload, timeout=10)
        
        logging.info(f"OpenAI status: {response.status_code}")
        
        if response.status_code != 200:
            logging.error(f"OpenAI error: {response.text}")
            return func.HttpResponse(
                json.dumps({"error": f"OpenAI error: {response.text[:100]}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        result = response.json()
        reply = result['choices'][0]['message']['content']
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "reply": reply
            }),
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Exception: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": f"Internal error: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )