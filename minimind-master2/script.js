import { register, login, sendMessage, getHistory, isAuthenticated, logout } from './api.js';

// 检查当前页面
const isLoginPage = window.location.pathname.includes('index.html');

// 登录页面逻辑
if (isLoginPage) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const tabBtns = document.querySelectorAll('.tab-btn');

    // Tab切换
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            if (targetTab === 'login') {
                loginForm.classList.remove('hidden');
                registerForm.classList.add('hidden');
            } else {
                registerForm.classList.remove('hidden');
                loginForm.classList.add('hidden');
            }
        });
    });

    // 登录表单提交
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await login(email, password);
            if (response.token) {
                localStorage.setItem('token', response.token);
                localStorage.setItem('userEmail', email);
                window.location.href = '/chat.html';
            } else {
                alert('登录失败：' + response.message);
            }
        } catch (error) {
            alert('登录出错：' + error.message);
        }
    });

    // 注册表单提交
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;

        if (password !== confirmPassword) {
            alert('两次输入的密码不一致');
            return;
        }

        try {
            const response = await register(email, password);
            if (response.success) {
                alert('注册成功，请登录');
                window.location.reload();
            } else {
                alert('注册失败：' + response.message);
            }
        } catch (error) {
            alert('注册出错：' + error.message);
        }
    });
}
// 聊天页面逻辑
else {
    // 检查登录状态
    if (!isAuthenticated()) {
        window.location.href = '/index.html';
    }

    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const historyList = document.getElementById('historyList');
    const logoutBtn = document.getElementById('logoutBtn');
    const userEmail = document.getElementById('userEmail');
    const newChatBtn = document.getElementById('newChatBtn');

    let currentConversationId = null;

    // 显示用户邮箱
    userEmail.textContent = localStorage.getItem('userEmail');

    // 加载历史记录
    async function loadHistory() {
        try {
            const history = await getHistory();
            historyList.innerHTML = '';
            history.forEach(conv => {
                const div = document.createElement('div');
                div.className = 'history-item';
                div.textContent = conv.title || '新对话';
                div.dataset.id = conv.id;
                div.onclick = () => loadConversation(conv.id);
                historyList.appendChild(div);
            });
        } catch (error) {
            console.error('加载历史记录失败：', error);
        }
    }

    // 加载特定对话
    async function loadConversation(conversationId) {
        currentConversationId = conversationId;
        // 这里需要后端提供获取特定对话内容的API
        chatMessages.innerHTML = '';
        // 加载对话内容...
    }

    // 发送消息
    async function handleSendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;

        // 显示用户消息
        const userDiv = document.createElement('div');
        userDiv.className = 'message user-message';
        userDiv.textContent = message;
        chatMessages.appendChild(userDiv);

        // 清空输入框
        messageInput.value = '';

        try {
            const response = await sendMessage(message, currentConversationId);
            
            // 显示AI回复
            const botDiv = document.createElement('div');
            botDiv.className = 'message bot-message';
            botDiv.textContent = response.reply;
            chatMessages.appendChild(botDiv);

            // 更新会话ID
            currentConversationId = response.conversation_id;
            
            // 如果是新对话，刷新历史记录
            if (!currentConversationId) {
                loadHistory();
            }
        } catch (error) {
            alert('发送消息失败：' + error.message);
        }
    }

    // 事件监听器
    sendBtn.onclick = handleSendMessage;
    messageInput.onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };
    logoutBtn.onclick = logout;
    newChatBtn.onclick = () => {
        currentConversationId = null;
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <h1>MiniMind Chat</h1>
                <p>开始一段新的对话吧！</p>
            </div>
        `;
    };

    // 初始加载
    loadHistory();
} 