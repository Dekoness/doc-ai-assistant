// URL de tu función Azure (¡CAMBIA ESTO!)
const AZURE_FUNCTION_URL = "https://docai-function-1994-b8ecg3cyfhake3gr.westeurope-01.azurewebsites.net/api/analyze_image_1994";

let currentImage = null;
let analysisResult = null;

// Manejar selección de archivo
document.getElementById('dropArea').addEventListener('click', () => {
    document.getElementById('fileInput').click();
});

document.getElementById('fileInput').addEventListener('change', (e) => {
    if (e.target.files[0]) {
        currentImage = e.target.files[0];
        document.getElementById('analyzeBtn').disabled = false;
        document.getElementById('dropArea').innerHTML = `✅ ${currentImage.name} seleccionado`;
    }
});

// Convertir imagen a Base64
function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = error => reject(error);
    });
}

// Analizar imagen con Azure
async function analyzeImage() {
    if (!currentImage) return;
    
    const analyzeBtn = document.getElementById('analyzeBtn');
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = 'Analizando...';
    
    try {
        // Convertir a Base64
        const base64Image = await toBase64(currentImage);
        
        // Llamar a Azure Function
        const response = await fetch(AZURE_FUNCTION_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                action: 'analyze',
                image: base64Image 
            })
        });
        
        if (!response.ok) {
            throw new Error(`Error HTTP: ${response.status}`);
        }
        
        analysisResult = await response.json();
        
        // Mostrar resultados
        displayResults(analysisResult);
        document.getElementById('result').style.display = 'block';
        
        analyzeBtn.textContent = '✅ Análisis completado';
        
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('analysisOutput').innerHTML = 
            `<p style="color: red;">Error: ${error.message}</p>`;
        analyzeBtn.textContent = '🔍 Analizar Imagen';
        analyzeBtn.disabled = false;
    }
}

// Mostrar resultados
function displayResults(data) {
    const output = document.getElementById('analysisOutput');
    
    if (data.type === 'document') {
        output.innerHTML = `
            <h4>📄 Documento detectado</h4>
            <p><strong>Texto extraído:</strong> ${data.data.text.substring(0, 200)}...</p>
            <p><em>${data.data.tables ? data.data.tables.length : 0} tablas detectadas</em></p>
        `;
    } else {
        output.innerHTML = `
            <h4>🎯 Objetos detectados</h4>
            <ul>
                ${data.data.objects_detected ? 
                    data.data.objects_detected.map(obj => 
                        `<li>${obj.object} (${Math.round(obj.confidence * 100)}%)</li>`
                    ).join('') : 
                    '<li>No se detectaron objetos específicos</li>'
                }
            </ul>
            <p><strong>Descripción:</strong> ${data.data.description || 'No disponible'}</p>
        `;
    }
    
    // Mostrar primera pregunta automática
    addChatMessage('system', 
        data.type === 'document' 
        ? 'He detectado un documento. ¿Sobre qué quieres que te ayude?' 
        : `Veo ${data.data.objects_detected?.length || 'varios'} objetos. ¿Qué te gustaría saber sobre ellos?`
    );
}

// Preguntar sobre la imagen
async function askQuestion() {
    const questionInput = document.getElementById('questionInput');
    const question = questionInput.value.trim();
    
    if (!question || !analysisResult) return;
    
    // Mostrar pregunta del usuario
    addChatMessage('user', question);
    questionInput.value = '';
    
    try {
        // Llamar a función de chat (la crearemos después)
        const response = await fetch(AZURE_FUNCTION_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                action: 'chat',
                question: question,
                image_context: analysisResult.chat_context
            })
        });
        
        const data = await response.json();
        addChatMessage('ai', data.answer || 'Lo siento, no puedo responder en este momento.');
        
    } catch (error) {
        addChatMessage('ai', `Error: ${error.message}`);
    }
}

// Añadir mensaje al chat
function addChatMessage(sender, text) {
    const chatHistory = document.getElementById('chatHistory');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.innerHTML = `<strong>${sender === 'user' ? '👤 Tú' : '🤖 AI'}:</strong> ${text}`;
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}