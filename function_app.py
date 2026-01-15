import azure.functions as func
import json
import base64
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from azure.ai.formrecognizer import DocumentAnalysisClient
from msrest.authentication import CognitiveServicesCredentials
import io

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="analyze_image")
def analyze_image(req: func.HttpRequest) -> func.HttpResponse:
    """Analiza imagen: decide si es documento u objeto"""
    
    # 1. Recibir imagen
    req_body = req.get_json()
    image_data = base64.b64decode(req_body['image'])
    
    # 2. Usar Computer Vision para clasificar
    vision_client = ComputerVisionClient(
        endpoint=os.environ["VISION_ENDPOINT"],
        credentials=CognitiveServicesCredentials(os.environ["VISION_KEY"])
    )
    
    # Analizar características
    analysis = vision_client.analyze_image_in_stream(
        image=io.BytesIO(image_data),
        visual_features=[
            VisualFeatureTypes.objects,      # Detección objetos
            VisualFeatureTypes.description,  # Descripción
            VisualFeatureTypes.tags,         # Etiquetas
            VisualFeatureTypes.categories    # Categorías
        ]
    )
    
    # 3. Decidir tipo de imagen
    is_document = any(cat.name == 'text_' for cat in analysis.categories)
    
    if is_document:
        # 4A. Si es documento: OCR avanzado
        form_client = DocumentAnalysisClient(
            endpoint=os.environ["FORM_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["FORM_KEY"])
        )
        
        poller = form_client.begin_analyze_document(
            "prebuilt-document", 
            document=io.BytesIO(image_data)
        )
        result = poller.result()
        
        # Extraer texto estructurado
        extracted_data = {
            "text": result.content if result.content else "",
            "tables": [table.to_dict() for table in result.tables],
            "key_value_pairs": [kv.to_dict() for kv in result.key_value_pairs]
        }
        
        response_type = "document"
        
    else:
        # 4B. Si es objeto: Descripción detallada
        extracted_data = {
            "objects_detected": [
                {
                    "object": obj.object_property,
                    "confidence": obj.confidence,
                    "bounding_box": [obj.rectangle.x, obj.rectangle.y, 
                                    obj.rectangle.w, obj.rectangle.h]
                }
                for obj in analysis.objects
            ],
            "description": analysis.description.captions[0].text if analysis.description.captions else "",
            "tags": [tag.name for tag in analysis.tags],
            "categories": [cat.name for cat in analysis.categories]
        }
        response_type = "object"
    
    # 5. Preparar contexto para el chat
    chat_context = {
        "image_type": response_type,
        "analysis": extracted_data,
        "raw_vision_analysis": analysis.as_dict() if hasattr(analysis, 'as_dict') else str(analysis)
    }
    
    return func.HttpResponse(
        json.dumps({
            "type": response_type,
            "data": extracted_data,
            "chat_context": chat_context
        }),
        mimetype="application/json"
    )

@app.route(route="chat_with_image")
def chat_with_image(req: func.HttpRequest) -> func.HttpResponse:
    """Chat con contexto de la imagen analizada"""
    req_body = req.get_json()
    
    # Contexto de la imagen previamente analizada
    image_context = req_body.get("image_context", {})
    user_question = req_body.get("question", "")
    
    # Construir prompt especializado
    if image_context.get("image_type") == "document":
        prompt = f"""Eres un experto en análisis de documentos. 

TEXTO EXTRAÍDO DEL DOCUMENTO:
{image_context.get('analysis', {}).get('text', '')}

INSTRUCCIONES ESPECIALES PARA DOCUMENTOS:
1. Responde preguntas sobre el contenido del documento
2. Identifica nombres propios, fechas, números importantes
3. Si preguntan por algo no en el documento, indícalo claramente

PREGUNTA: {user_question}

RESPUESTA:"""
    
    else:  # Es objeto
        prompt = f"""Eres un experto en reconocimiento visual y descripción de objetos.

ANÁLISIS DE LA IMAGEN:
- Objetos detectados: {image_context.get('analysis', {}).get('objects_detected', [])}
- Descripción general: {image_context.get('analysis', {}).get('description', '')}
- Etiquetas relevantes: {image_context.get('analysis', {}).get('tags', [])}

INSTRUCCIONES ESPECIALES PARA OBJETOS:
1. Describe detalladamente lo que ves
2. Proporciona información útil sobre los objetos detectados  
3. Si es un objeto específico (coche, edificio, etc.), da datos interesantes
4. Sé entusiasta y descriptivo

PREGUNTA: {user_question}

RESPUESTA:"""
    
    # Aquí conectarías a Ollama local o Azure OpenAI
    # (Usaremos la misma lógica de fallback anterior)
    
    return func.HttpResponse(
        json.dumps({"answer": "Respuesta del modelo", "context_used": image_context.get("image_type")}),
        mimetype="application/json"
    )