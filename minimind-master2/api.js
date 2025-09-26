// API 基础URL
const API_BASE_URL = 'http://localhost:5000/api';

// 用户认证相关API
export async function register(email, password) {
    const response = await fetch(`${API_BASE_URL}/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
    });
    return response.json();
}

export async function login(email, password) {
    const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
    });
    return response.json();
}

// 聊天相关API
export async function sendMessage(message, conversationId = null) {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
            message,
            conversation_id: conversationId,
        }),
    });
    return response.json();
}

export async function getHistory() {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/history`, {
        headers: {
            'Authorization': `Bearer ${token}`,
        },
    });
    return response.json();
}

// 工具函数
export function isAuthenticated() {
    return !!localStorage.getItem('token');
}

export function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    window.location.href = '/index.html';
} 