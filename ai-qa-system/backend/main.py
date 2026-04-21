"""Main FastAPI application for AI Q&A System."""

import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.config import settings
from backend.models import HealthResponse
from backend.routers import chat, documents, langchain_rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting AI Q&A System...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"RAG Enabled: {settings.rag_enabled}")
    yield
    logger.info("Shutting down AI Q&A System...")


# Create FastAPI app
app = FastAPI(
    title="AI Q&A System",
    description="An intelligent question-answering system powered by large language models",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(langchain_rag.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Q&A System</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                width: 100%;
                max-width: 900px;
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2rem;
                margin-bottom: 10px;
            }
            
            .header p {
                opacity: 0.9;
                font-size: 1rem;
            }
            
            .chat-container {
                height: 500px;
                overflow-y: auto;
                padding: 20px;
                background: #f8f9fa;
            }
            
            .message {
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
            }
            
            .message.user {
                align-items: flex-end;
            }
            
            .message.assistant {
                align-items: flex-start;
            }
            
            .message-content {
                max-width: 70%;
                padding: 15px 20px;
                border-radius: 15px;
                line-height: 1.5;
            }
            
            .message.user .message-content {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-bottom-right-radius: 5px;
            }
            
            .message.assistant .message-content {
                background: white;
                color: #333;
                border: 1px solid #e0e0e0;
                border-bottom-left-radius: 5px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }
            
            .input-container {
                padding: 20px;
                background: white;
                border-top: 1px solid #e0e0e0;
                display: flex;
                gap: 10px;
            }
            
            .input-container input {
                flex: 1;
                padding: 15px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 25px;
                font-size: 1rem;
                outline: none;
                transition: border-color 0.3s;
            }
            
            .input-container input:focus {
                border-color: #667eea;
            }
            
            .input-container button {
                padding: 15px 30px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 1rem;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .input-container button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            
            .input-container button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            
            .options {
                padding: 10px 20px;
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                flex-wrap: wrap;
            }
            
            .options-left {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .options label {
                display: flex;
                align-items: center;
                gap: 5px;
                cursor: pointer;
                font-size: 0.9rem;
                color: #666;
            }
            
            .upload-btn {
                padding: 8px 16px;
                background: #28a745;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 0.85rem;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                display: flex;
                align-items: center;
                gap: 5px;
            }
            
            .upload-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 3px 10px rgba(40, 167, 69, 0.4);
            }
            
            .upload-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            
            .file-input {
                display: none;
            }
            
            .upload-status {
                font-size: 0.85rem;
                color: #666;
                padding: 5px 10px;
                border-radius: 10px;
                background: #e9ecef;
            }
            
            .upload-status.success {
                background: #d4edda;
                color: #155724;
            }
            
            .upload-status.error {
                background: #f8d7da;
                color: #721c24;
            }
            
            .loading {
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            
            .loading-spinner {
                width: 30px;
                height: 30px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .sources {
                margin-top: 10px;
                padding: 10px;
                background: #f0f0f0;
                border-radius: 10px;
                font-size: 0.85rem;
            }
            
            .sources h4 {
                color: #666;
                margin-bottom: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 AI Q&A System</h1>
                <p>Ask me anything!</p>
            </div>
            <div class="chat-container" id="chatContainer">
                <div class="message assistant">
                    <div class="message-content">
                        Hello! I'm your AI assistant. Ask me anything or enable RAG for context-aware answers based on uploaded documents.
                    </div>
                </div>
            </div>
            <div class="options">
                <div class="options-left">
                    <label>
                        <input type="checkbox" id="useRag">
                        Use Knowledge Base (RAG)
                    </label>
                </div>
                <div class="options-right">
                    <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                        📁 Upload Document
                    </button>
                    <input type="file" id="fileInput" class="file-input" accept=".txt,.pdf,.md" onchange="uploadDocument(event)" />
                    <span id="uploadStatus" class="upload-status" style="display: none;"></span>
                </div>
            </div>
            <div class="input-container">
                <input type="text" id="messageInput" placeholder="Type your message..." />
                <button id="sendButton" onclick="sendMessage()">Send</button>
            </div>
        </div>
        
        <script>
            let sessionId = null;
            
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            async function uploadDocument(event) {
                const file = event.target.files[0];
                if (!file) return;
                
                const uploadBtn = document.querySelector('.upload-btn');
                const statusEl = document.getElementById('uploadStatus');
                
                // Show status
                statusEl.style.display = 'inline';
                statusEl.textContent = 'Uploading...';
                statusEl.className = 'upload-status';
                uploadBtn.disabled = true;
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    const response = await fetch('/api/documents/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        statusEl.textContent = `✓ Uploaded: ${data.filename} (${data.chunks_added} chunks)`;
                        statusEl.className = 'upload-status success';
                    } else {
                        throw new Error(data.detail || 'Upload failed');
                    }
                } catch (error) {
                    statusEl.textContent = '✗ Upload failed: ' + error.message;
                    statusEl.className = 'upload-status error';
                }
                
                uploadBtn.disabled = false;
                
                // Clear file input
                event.target.value = '';
                
                // Hide status after 5 seconds
                setTimeout(() => {
                    statusEl.style.display = 'none';
                }, 5000);
            }
            
            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const button = document.getElementById('sendButton');
                const useRag = document.getElementById('useRag').checked;
                const message = input.value.trim();
                
                if (!message) return;
                
                // Clear input and disable button
                input.value = '';
                button.disabled = true;
                
                // Add user message
                addMessage(message, 'user');
                
                // Show loading
                showLoading();
                
                try {
                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            message: message,
                            session_id: sessionId,
                            use_rag: useRag
                        })
                    });
                    
                    const data = await response.json();
                    hideLoading();
                    
                    // Update session ID
                    sessionId = data.session_id;
                    
                    // Add assistant message
                    addMessage(data.response, 'assistant');
                    
                    // Show sources if available
                    if (data.sources && data.sources.length > 0) {
                        showSources(data.sources);
                    }
                } catch (error) {
                    hideLoading();
                    addMessage('Error: ' + error.message, 'assistant');
                }
                
                button.disabled = false;
                input.focus();
            }
            
            function addMessage(content, role) {
                const container = document.getElementById('chatContainer');
                const div = document.createElement('div');
                div.className = 'message ' + role;
                div.innerHTML = '<div class="message-content">' + content + '</div>';
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }
            
            function showLoading() {
                const container = document.getElementById('chatContainer');
                const div = document.createElement('div');
                div.className = 'loading';
                div.id = 'loading';
                div.innerHTML = '<div class="loading-spinner"></div>';
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }
            
            function hideLoading() {
                const loading = document.getElementById('loading');
                if (loading) loading.remove();
            }
            
            function showSources(sources) {
                const container = document.getElementById('chatContainer');
                const div = document.createElement('div');
                div.className = 'sources';
                div.innerHTML = '<h4>Sources:</h4>' + sources.map(s => 
                    '<div>' + s.content.substring(0, 100) + '...</div>'
                ).join('');
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_provider=settings.llm_provider,
        rag_enabled=settings.rag_enabled
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )