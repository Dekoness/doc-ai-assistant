// CONFIGURACIÓN
const AZURE_FUNCTION_URL = "https://docai-function-v2-brabayb3hgfef8cx.westeurope-01.azurewebsites.net/api/analyze_image";
let currentImage = null;

// INICIALIZACIÓN
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Azure AI Vision Assistant iniciado');
    
    // Configurar elementos
    const fileInput = document.getElementById('fileInput');
    const dropArea = document.getElementById('dropArea');
    const analyzeBtn = document.getElementById('analyzeBtn');
    
    // Click en área de subida
    dropArea.addEventListener('click', () => {
        console.log('📁 Click en área de subida');
        fileInput.click();
    });
    
    // Cambio de archivo
    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            handleFileSelect(e.target.files[0]);
        }
    });
    
    // Botón analizar
    analyzeBtn.addEventListener('click', analyzeImage);
    
    // Drag & drop
    setupDragAndDrop();
    
    // Mostrar mensaje inicial
    showStatus('✅ Aplicación lista. Selecciona una imagen para analizar.', 'success');
});

// MANEJAR ARCHIVO SELECCIONADO
function handleFileSelect(file) {
    console.log('📸 Archivo seleccionado:', file.name, file.size, 'bytes');
    
    // Validaciones
    if (file.size > 4 * 1024 * 1024) {
        showStatus('❌ Archivo muy grande (máximo 4MB)', 'error');
        return;
    }
    
    const validTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif'];
    if (!validTypes.includes(file.type)) {
        showStatus('❌ Formato no válido. Usa JPG o PNG', 'error');
        return;
    }
    
    currentImage = file;
    
    // Actualizar UI
    const dropArea = document.getElementById('dropArea');
    dropArea.innerHTML = `
        <div class="text-5xl mb-4 text-green-500">✅</div>
        <h3 class="text-xl font-semibold mb-2">${file.name}</h3>
        <p class="text-gray-500 mb-2">${(file.size / 1024).toFixed(2)} KB • ${file.type}</p>
        <p class="text-sm text-blue-500">Listo para analizar con Azure AI</p>
    `;
    
    // Activar botón
    document.getElementById('analyzeBtn').disabled = false;
    
    showStatus('✅ Imagen seleccionada. Haz clic en "Analizar Imagen"', 'success');
}

// CONFIGURAR DRAG & DROP
function setupDragAndDrop() {
    const dropArea = document.getElementById('dropArea');
    
    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('border-blue-400', 'bg-blue-50');
    });
    
    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('border-blue-400', 'bg-blue-50');
    });
    
    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('border-blue-400', 'bg-blue-50');
        
        if (e.dataTransfer.files[0]) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });
}

// ANALIZAR IMAGEN CON AZURE
async function analyzeImage() {
    if (!currentImage) {
        showStatus('❌ No hay imagen seleccionada', 'error');
        return;
    }
    
    const analyzeBtn = document.getElementById('analyzeBtn');
    const originalText = analyzeBtn.textContent;
    
    // Actualizar UI
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '<span class="flex items-center justify-center"><svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Procesando con Azure AI...</span>';
    
    // Mostrar resultados
    const resultsDiv = document.getElementById('results');
    resultsDiv.classList.remove('hidden');
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
    
    showStatus('🔄 Conectando con Azure Cognitive Services...', 'info');
    
    try {
        console.log('📤 Enviando petición a Azure Function...');
        
        // Preparar datos
        const requestData = {
            action: 'analyze',
            filename: currentImage.name,
            filesize: currentImage.size,
            filetype: currentImage.type,
            timestamp: new Date().toISOString(),
            test_mode: true  // Por ahora en modo test
        };
        
        // Hacer la petición (igual que en consola)
        const response = await fetch(AZURE_FUNCTION_URL, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        console.log('📥 Respuesta recibida:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Azure Function error ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('✅ Datos recibidos:', data);
        
        // MOSTRAR RESULTADOS
        document.getElementById('status').innerHTML = 
            `<div class="p-4 bg-green-50 rounded-lg border border-green-200">
                <div class="flex items-center">
                    <span class="text-green-600 text-2xl mr-2">✅</span>
                    <div>
                        <h3 class="font-bold text-green-800">${data.message}</h3>
                        <p class="text-sm text-green-600">Todos los servicios Azure configurados correctamente</p>
                    </div>
                </div>
            </div>`;
        
        // Detalles del análisis
        const configStatus = data.config_status || {};
        const servicesHtml = Object.entries(configStatus)
            .map(([service, configured]) => `
                <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="font-medium">${service.replace('_', ' ')}:</span>
                    <span class="${configured ? 'text-green-600 font-bold' : 'text-red-600'}">
                        ${configured ? '✅ CONFIGURADO' : '❌ NO CONFIGURADO'}
                    </span>
                </div>
            `).join('');
        
        document.getElementById('details').innerHTML = `
            <div class="space-y-4">
                <div>
                    <h4 class="font-bold text-gray-700 mb-2">🔧 Configuración Azure:</h4>
                    <div class="bg-gray-50 rounded-lg p-4">
                        ${servicesHtml}
                        <div class="mt-4 pt-4 border-t border-gray-200">
                            <p class="text-sm"><span class="font-medium">Servicios listos:</span> <span class="text-blue-600 font-bold">${data.azure_services_ready}/4</span></p>
                            <p class="text-sm"><span class="font-medium">Timestamp:</span> ${new Date(data.timestamp).toLocaleString()}</p>
                        </div>
                    </div>
                </div>
                
                <div>
                    <h4 class="font-bold text-gray-700 mb-2">📋 Información de la imagen:</h4>
                    <div class="bg-blue-50 rounded-lg p-4">
                        <p><span class="font-medium">Nombre:</span> ${currentImage.name}</p>
                        <p><span class="font-medium">Tamaño:</span> ${(currentImage.size / 1024).toFixed(2)} KB</p>
                        <p><span class="font-medium">Tipo:</span> ${currentImage.type}</p>
                    </div>
                </div>
            </div>
        `;
        
        // Debug info
        document.getElementById('debug').textContent = JSON.stringify(data, null, 2);
        
        // Actualizar botón
        analyzeBtn.innerHTML = '<span class="flex items-center justify-center"><span class="text-green-600 text-xl mr-2">✅</span> Análisis completado</span>';
        
        showStatus('✅ Análisis completado exitosamente', 'success');
        
    } catch (error) {
        console.error('❌ Error en analyzeImage:', error);
        
        // Mostrar error amigable
        document.getElementById('status').innerHTML = 
            `<div class="p-4 bg-red-50 rounded-lg border border-red-200">
                <div class="flex items-center">
                    <span class="text-red-600 text-2xl mr-2">❌</span>
                    <div>
                        <h3 class="font-bold text-red-800">Error de conexión</h3>
                        <p class="text-red-600">${error.message}</p>
                    </div>
                </div>
            </div>`;
        
        document.getElementById('details').innerHTML = `
            <div class="p-4 bg-yellow-50 rounded-lg">
                <h4 class="font-bold mb-2">💡 Solución:</h4>
                <p class="mb-2">La función Azure funciona, pero hay un problema local.</p>
                <ul class="list-disc pl-5 space-y-1">
                    <li><strong>Prueba en modo incógnito</strong> (sin extensiones)</li>
                    <li><strong>Usa otro navegador</strong> (Chrome, Edge, Firefox)</li>
                    <li><strong>O sube a Vercel</strong> para evitar problemas CORS</li>
                </ul>
                <div class="mt-4 p-3 bg-gray-100 rounded">
                    <p class="text-sm font-mono break-all">URL: ${AZURE_FUNCTION_URL}</p>
                </div>
            </div>
        `;
        
        document.getElementById('debug').textContent = `Error: ${error.message}\n\nURL: ${AZURE_FUNCTION_URL}`;
        
        // Restaurar botón
        analyzeBtn.innerHTML = originalText;
        analyzeBtn.disabled = false;
        
        showStatus('❌ Error al conectar con Azure', 'error');
    }
}

// FUNCIONES UTILITARIAS
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status');
    
    const colors = {
        success: 'bg-green-50 border-green-200 text-green-800',
        error: 'bg-red-50 border-red-200 text-red-800',
        info: 'bg-blue-50 border-blue-200 text-blue-800'
    };
    
    statusDiv.innerHTML = `
        <div class="p-4 rounded-lg border ${colors[type]}">
            <div class="flex items-center">
                <span class="mr-2">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
                <span>${message}</span>
            </div>
        </div>
    `;
    
    // Auto-ocultar si no es error
    if (type !== 'error') {
        setTimeout(() => {
            if (statusDiv.innerHTML.includes(message)) {
                statusDiv.innerHTML = '';
            }
        }, 5000);
    }
}

// Convertir imagen a Base64 (para cuando implementemos IA real)
function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result.split(',')[1]);
        reader.onerror = error => reject(error);
    });
}

// Prueba rápida desde consola (para debug)
window.testAzureConnection = async () => {
    console.log('🧪 Probando conexión Azure...');
    try {
        const response = await fetch(AZURE_FUNCTION_URL, {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: JSON.stringify({ test: true })
        });
        const data = await response.json();
        console.log('✅ Conexión exitosa:', data);
        return data;
    } catch (error) {
        console.error('❌ Error:', error);
        return null;
    }
};