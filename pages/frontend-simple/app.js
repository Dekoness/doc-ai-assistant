const AZURE_FUNCTION_URL = "https://docai-function-1994-b8ecg3cyfhake3gr.westeurope-01.azurewebsites.net/api/analyze_image_1994";

// Configuración para debug
const DEBUG_MODE = true;

async function analyzeImage() {
    if (!currentImage) return;
    
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analizando...';
    
    try {
        if (DEBUG_MODE) {
            console.log('🔍 Modo DEBUG activado - Usando datos de prueba');
            
            // Datos de prueba para desarrollo
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const isDocument = Math.random() > 0.5;
            if (isDocument) {
                analysisResult = {
                    "type": "document",
                    "data": {
                        "text": "Este es un texto de ejemplo extraído de un documento real usando Azure Form Recognizer. Contiene información importante que puede ser analizada por la IA.",
                        "tables": [{"rows": 3, "columns": 2}],
                        "key_value_pairs": [{"key": "Fecha", "value": "2024-01-15"}]
                    },
                    "chat_context": {
                        "image_type": "document",
                        "extracted_text": "Texto de ejemplo para contexto de chat..."
                    }
                };
            } else {
                analysisResult = {
                    "type": "object",
                    "data": {
                        "objects_detected": [
                            {"object": "coche", "confidence": 0.95},
                            {"object": "persona", "confidence": 0.87},
                            {"object": "edificio", "confidence": 0.78}
                        ],
                        "description": "Una persona junto a un coche frente a un edificio moderno",
                        "tags": ["vehículo", "persona", "arquitectura", "exterior"],
                        "categories": ["transporte", "gente", "urbano"]
                    },
                    "chat_context": {
                        "image_type": "object",
                        "description": "Persona junto a coche frente a edificio"
                    }
                };
            }
            
            displayResults(analysisResult);
            document.getElementById('result').style.display = 'block';
            analyzeBtn.textContent = '✅ Análisis completado (DEBUG)';
            
        } else {
            // Código real para producción
            const base64Image = await toBase64(currentImage);
            
            const response = await fetch(AZURE_FUNCTION_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    action: 'analyze',
                    image: base64Image 
                })
            });
            
            if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);
            
            analysisResult = await response.json();
            displayResults(analysisResult);
            document.getElementById('result').style.display = 'block';
            analyzeBtn.textContent = '✅ Análisis completado';
        }
        
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('analysisOutput').innerHTML = 
            `<p style="color: red;">Error: ${error.message}</p>
             <p><small>Modo DEBUG activado. La función Azure está configurada pero necesita CORS.</small></p>`;
        analyzeBtn.textContent = '🔍 Analizar Imagen';
        analyzeBtn.disabled = false;
    }
}