/* ============================================
   DeepSeek Q&A System - Frontend JavaScript
   ============================================ */

const API_BASE_URL = 'http://localhost:8000/api';
let currentSessionId = null;
let allSessions = {};

// DOM Elements
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const messagesArea = document.getElementById('messagesArea');
const newSessionBtn = document.getElementById('newSessionBtn');
const sessionsList = document.getElementById('sessionsList');
const loadingSpinner = document.getElementById('loadingSpinner');
const inputStatus = document.getElementById('inputStatus');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DeepSeek Q&A System initialized');
    
    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', handleKeyDown);
    newSessionBtn.addEventListener('click', createNewSession);
    
    // Auto-focus input
    messageInput.focus();
    
    // Load initial session
    createNewSession();
    loadSessions();
});

// Handle Enter key in textarea
function handleKeyDown(event) {
    if (event.key === 'Enter') {
        if (event.shiftKey) {
            // Shift+Enter: send message
            event.preventDefault();
            sendMessage();
        } else {
            // Regular Enter: new line (default behavior)
        }
    }
}

// Send message to backend
async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) {
        showStatus('请输入消息', 'error');
        return;
    }
    
    if (!currentSessionId) {
        showStatus('会话未初始化', 'error');
        return;
    }
    
    // Disable input
    messageInput.disabled = true;
    sendBtn.disabled = true;
    showLoading(true);
    
    // Add user message to UI
    addMessageToUI('user', message);
    messageInput.value = '';
    messageInput.style.height = '48px';
    
    try {
        // Send request
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                session_id: currentSessionId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP Error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update session ID if new
        if (data.session_id !== currentSessionId) {
            currentSessionId = data.session_id;
        }
        
        // Add assistant message to UI
        addMessageToUI('assistant', data.response);
        
        showStatus('消息已发送', 'success');
        
    } catch (error) {
        console.error('Error:', error);
        showStatus(`错误: ${error.message}`, 'error');
        // Add error message to UI
        addMessageToUI('assistant', `⚠️ 发生错误: ${error.message}`);
    } finally {
        // Re-enable input
        messageInput.disabled = false;
        sendBtn.disabled = false;
        messageInput.focus();
        showLoading(false);
        
        // Refresh sessions list
        loadSessions();
    }
}

// Add message to chat UI
function addMessageToUI(role, content) {
    // Remove welcome message if exists
    const welcomeMsg = messagesArea.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    messagesArea.appendChild(messageDiv);
    
    // Scroll to bottom
    scrollToBottom();
}

// Scroll messages area to bottom
function scrollToBottom() {
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

// Create new session
async function createNewSession() {
    try {
        showLoading(true);
        
        const response = await fetch(`${API_BASE_URL}/session/new`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`Failed to create session: ${response.status}`);
        }
        
        const data = await response.json();
        currentSessionId = data.session_id;
        
        // Clear messages area
        messagesArea.innerHTML = `
            <div class="welcome-message">
                <h2>👋 欢迎使用 DeepSeek 问答系统</h2>
                <p>开始提问，与 AI 助手进行对话</p>
                <div class="example-prompts">
                    <p style="font-size: 0.9em; color: #999; margin-top: 20px;">示例问题：</p>
                    <button class="example-btn" onclick="askQuestion('请解释一下什么是人工智能？')">什么是人工智能？</button>
                    <button class="example-btn" onclick="askQuestion('如何学习编程？')">如何学习编程？</button>
                    <button class="example-btn" onclick="askQuestion('请介绍一下DeepSeek模型的特点')">DeepSeek模型特点</button>
                </div>
            </div>
        `;
        
        messageInput.value = '';
        messageInput.focus();
        
        // Reload sessions
        await loadSessions();
        
        showStatus('已创建新会话', 'success');
        
    } catch (error) {
        console.error('Error creating session:', error);
        showStatus(`创建会话失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Load all sessions
async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE_URL}/sessions`);
        
        if (!response.ok) {
            throw new Error(`Failed to load sessions: ${response.status}`);
        }
        
        const data = await response.json();
        const sessions = data.sessions || [];
        
        // Sort by updated_at descending
        sessions.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
        
        // Update sidebar
        sessionsList.innerHTML = '';
        
        sessions.forEach(session => {
            const sessionItem = createSessionItem(session);
            sessionsList.appendChild(sessionItem);
        });
        
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

// Create session item element
function createSessionItem(session) {
    const div = document.createElement('div');
    div.className = `session-item ${session.session_id === currentSessionId ? 'active' : ''}`;
    
    const title = document.createElement('div');
    title.className = 'session-item-title';
    title.textContent = `Session ${session.session_id.substring(0, 8)}...`;
    
    const info = document.createElement('div');
    info.className = 'session-item-info';
    const date = new Date(session.updated_at);
    info.textContent = `${session.message_count} 条消息 • ${date.toLocaleDateString('zh-CN')}`;
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'session-item-delete';
    deleteBtn.textContent = '删除';
    deleteBtn.onclick = (e) => {
        e.stopPropagation();
        deleteSession(session.session_id);
    };
    
    div.appendChild(title);
    div.appendChild(info);
    div.appendChild(deleteBtn);
    
    div.onclick = () => switchSession(session.session_id);
    
    return div;
}

// Switch to different session
async function switchSession(sessionId) {
    try {
        showLoading(true);
        currentSessionId = sessionId;
        
        // Load chat history
        const response = await fetch(`${API_BASE_URL}/history/${sessionId}`);
        
        if (!response.ok) {
            throw new Error(`Failed to load history: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Clear and rebuild messages area
        messagesArea.innerHTML = '';
        
        data.messages.forEach(msg => {
            addMessageToUI(msg.role, msg.content);
        });
        
        // Update active session in sidebar
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelectorAll('.session-item').forEach(item => {
            if (item.textContent.includes(sessionId.substring(0, 8))) {
                item.classList.add('active');
            }
        });
        
        messageInput.focus();
        
    } catch (error) {
        console.error('Error switching session:', error);
        showStatus(`加载会话失败: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Delete session
async function deleteSession(sessionId) {
    if (!confirm('是否确认删除此会话？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/session/${sessionId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error(`Failed to delete session: ${response.status}`);
        }
        
        showStatus('会话已删除', 'success');
        
        // If deleted current session, create new one
        if (sessionId === currentSessionId) {
            createNewSession();
        } else {
            loadSessions();
        }
        
    } catch (error) {
        console.error('Error deleting session:', error);
        showStatus(`删除会话失败: ${error.message}`, 'error');
    }
}

// Ask a question (for example buttons)
function askQuestion(question) {
    messageInput.value = question;
    messageInput.focus();
    sendMessage();
}

// Show/hide loading spinner
function showLoading(show) {
    loadingSpinner.style.display = show ? 'block' : 'none';
}

// Show status message
function showStatus(message, type = 'info') {
    const statusColor = {
        'success': '#52c41a',
        'error': '#ff4d4f',
        'info': '#1890ff'
    };
    
    inputStatus.textContent = message;
    inputStatus.style.color = statusColor[type] || statusColor['info'];
    
    // Auto-clear after 3 seconds
    setTimeout(() => {
        inputStatus.textContent = '';
    }, 3000);
}

// Handle textarea auto-resize
messageInput.addEventListener('input', () => {
    messageInput.style.height = '48px';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
});
