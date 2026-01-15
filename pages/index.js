import { useState } from 'react';

export default function MultiAI() {
  const [analysis, setAnalysis] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  
  const handleImageUpload = async (file) => {
    // 1. Convertir a base64
    const base64 = await toBase64(file);
    
    // 2. Enviar a Azure Function
    const response = await fetch('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ image: base64 })
    });
    
    const data = await response.json();
    setAnalysis(data);
    
    // 3. Auto-pregunta según tipo
    if (data.type === 'document') {
      addMessage('system', 'He detectado un documento. ¿Sobre qué quieres que te ayude?');
    } else {
      addMessage('system', `Veo ${data.data.objects_detected?.length || 'varios'} objetos. ¿Qué te gustaría saber?`);
    }
  };
  
  const askAboutImage = async (question) => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        image_context: analysis.chat_context,
        question: question
      })
    });
    
    const data = await response.json();
    addMessage('assistant', data.answer);
  };
  
  return (
    <div>
      <h1>🧠 AI Vision Assistant</h1>
      <input type="file" accept="image/*" onChange={handleImageUpload} />
      
      {analysis && (
        <div>
          <h2>📊 Análisis:</h2>
          {analysis.type === 'document' ? (
            <div>
              <h3>📄 Documento detectado</h3>
              <p>{analysis.data.text.substring(0, 200)}...</p>
            </div>
          ) : (
            <div>
              <h3>🎯 Objetos detectados</h3>
              <ul>
                {analysis.data.objects_detected?.map((obj, i) => (
                  <li key={i}>{obj.object} ({Math.round(obj.confidence*100)}%)</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}